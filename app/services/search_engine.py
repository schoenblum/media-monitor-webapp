"""Core search-engine logic.

Ported from ``media_monitor_v38a.txt`` and made async + multi-tenant.

Each Run executes ``execute_run`` in the background:

1. Loads the Search (including terms + linked outlets) and the user's encrypted
   Google credentials.
2. Computes ``days_since`` from the most recent prior Run for the same Search.
3. For each linked, active outlet, and for each enabled term in the outlet's
   ``keyword_langs``, issues paginated Google CSE queries.
4. Persists every new ``Result`` row as it is found; on quota / HTTP 429,
   marks the run failed and returns early with all results saved.
"""
import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models.outlet import Outlet, SearchOutletLink
from app.models.result import Result
from app.models.run import Run, RunStatus
from app.models.search import Search, SearchTerm
from app.models.user import User
from app.services.crypto import decrypt
from app.services.date_extractor import extract_date
from app.services.default_outlets import EXCLUDED_DOMAINS
from app.services.lang_detector import detect_language


logger = logging.getLogger(__name__)

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
API_CALL_DELAY_SECONDS = 0.5
DEFAULT_LOOKBACK_DAYS = 7
MAX_PAGES = 10


def _is_excluded_url(url: str, user_outlet_domains: set[str]) -> bool:
    """Drop social-media URLs and any URL pointing at one of the user's own outlets
    via the same host as a different outlet (we already de-dupe by URL string)."""
    url_lower = url.lower()
    return any(d in url_lower for d in EXCLUDED_DOMAINS)


def _normalise_domain(domain: str) -> str:
    """Strip protocol / trailing slash / 'site:' prefix from an outlet domain."""
    d = domain.strip().lower()
    for prefix in ("https://", "http://", "site:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/")


async def _fetch_page(
    client: httpx.AsyncClient,
    api_key: str,
    engine_id: str,
    query: str,
    start: int,
    days: int,
) -> tuple[list[dict], bool, str | None]:
    """Fetch one CSE page. Returns ``(items, quota_hit, error_message)``."""
    params = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": 10,
        "start": start,
        "dateRestrict": f"d{max(1, days)}",
    }
    try:
        resp = await client.get(GOOGLE_CSE_URL, params=params, timeout=30.0)
    except httpx.HTTPError as exc:
        return [], False, f"HTTP error: {exc}"

    if resp.status_code == 429:
        return [], True, "Google CSE returned HTTP 429 (quota exceeded)"

    try:
        payload = resp.json()
    except ValueError:
        return [], False, f"Non-JSON response from Google CSE (status {resp.status_code})"

    if resp.status_code >= 400:
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = err.get("message", f"HTTP {resp.status_code}")
        if "quota" in str(message).lower() or resp.status_code == 403:
            return [], True, f"Quota / auth error: {message}"
        return [], False, str(message)

    return payload.get("items", []) or [], False, None


async def _compute_lookback_days(db: AsyncSession, search_id: UUID, current_run_id: UUID) -> int:
    """Days between the most recent *prior* completed run of this Search and now."""
    stmt = (
        select(Run.started_at)
        .where(Run.search_id == search_id)
        .where(Run.id != current_run_id)
        .where(Run.status == RunStatus.complete)
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    prev_started: datetime | None = res.scalar_one_or_none()
    if prev_started is None:
        return DEFAULT_LOOKBACK_DAYS
    now = datetime.now(timezone.utc)
    if prev_started.tzinfo is None:
        prev_started = prev_started.replace(tzinfo=timezone.utc)
    return max(1, (now - prev_started).days)


async def execute_run(run_id: UUID) -> None:
    """Run a search in the background. Opens its own DB session.

    Always commits a final status (``complete`` or ``failed``) and never raises.
    Partial results collected before a quota / fatal error are preserved.
    """
    async with SessionLocal() as db:
        try:
            await _execute_run_inner(run_id, db)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Run %s crashed: %s", run_id, exc)
            await _mark_failed(db, run_id, f"Internal error: {exc}")


async def _mark_failed(db: AsyncSession, run_id: UUID, message: str) -> None:
    run = await db.get(Run, run_id)
    if run is None:
        return
    run.status = RunStatus.failed
    run.error_message = message[:1900]
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()


async def _execute_run_inner(run_id: UUID, db: AsyncSession) -> None:
    run = await db.get(Run, run_id)
    if run is None:
        logger.warning("Run %s vanished before execution", run_id)
        return

    run.status = RunStatus.running
    await db.commit()

    # Load the search with terms + linked outlets.
    stmt = (
        select(Search)
        .where(Search.id == run.search_id)
        .options(
            selectinload(Search.terms),
            selectinload(Search.outlet_links).selectinload(SearchOutletLink.outlet),
        )
    )
    search = (await db.execute(stmt)).scalar_one_or_none()
    if search is None:
        await _mark_failed(db, run_id, "Search not found")
        return

    user = await db.get(User, run.user_id)
    if user is None:
        await _mark_failed(db, run_id, "User not found")
        return

    if not user.google_api_key_encrypted or not user.search_engine_id_encrypted:
        await _mark_failed(
            db,
            run_id,
            "Google API credentials not configured. Add them in Settings.",
        )
        return

    try:
        api_key = decrypt(user.google_api_key_encrypted)
        engine_id = decrypt(user.search_engine_id_encrypted)
    except Exception as exc:  # noqa: BLE001
        await _mark_failed(db, run_id, f"Failed to decrypt API credentials: {exc}")
        return

    # Build lookup: language → (term, pages, enabled).
    terms_by_lang: dict[str, SearchTerm] = {t.language_code: t for t in search.terms}

    # Active outlets linked to this search.
    outlets: list[Outlet] = [
        link.outlet for link in search.outlet_links if link.outlet and link.outlet.is_active
    ]
    user_outlet_domains = {_normalise_domain(o.domain) for o in outlets}

    if not outlets:
        run.status = RunStatus.complete
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = "No active outlets linked to this search."
        await db.commit()
        return

    days_since = await _compute_lookback_days(db, search.id, run.id)
    seen_urls: set[str] = set()
    api_calls_used = 0
    quota_hit = False
    last_error: str | None = None

    async with httpx.AsyncClient() as client:
        for outlet in outlets:
            if quota_hit:
                break

            domain = _normalise_domain(outlet.domain)
            for lang in outlet.keyword_langs or []:
                if quota_hit:
                    break
                term_row = terms_by_lang.get(lang)
                if term_row is None or not term_row.is_enabled or not term_row.term.strip():
                    continue
                pages = max(1, min(MAX_PAGES, term_row.pages))
                keyword = term_row.term.strip()
                query = f'"{keyword}" site:{domain}'

                for page in range(pages):
                    start = page * 10 + 1
                    items, quota, err = await _fetch_page(
                        client, api_key, engine_id, query, start, days_since
                    )
                    api_calls_used += 1

                    if quota:
                        quota_hit = True
                        last_error = err
                        break
                    if err:
                        last_error = err
                        logger.warning(
                            "Outlet %s lang=%s page=%d: %s", outlet.name, lang, page + 1, err
                        )
                        break
                    if not items:
                        break

                    new_rows = []
                    for item in items:
                        url = item.get("link", "")
                        if not url or url in seen_urls:
                            continue
                        if _is_excluded_url(url, user_outlet_domains):
                            continue
                        seen_urls.add(url)
                        title = item.get("title", "No title")
                        snippet = item.get("snippet", "") or ""
                        dl_code, dl_name = detect_language(title, snippet)
                        new_rows.append(
                            Result(
                                run_id=run.id,
                                outlet_name=outlet.name,
                                title=title,
                                url=url,
                                display_source=item.get("displayLink", "") or "",
                                snippet=snippet,
                                date_extracted=extract_date(snippet),
                                keyword_used=keyword,
                                search_lang=lang,
                                detected_lang=dl_code,
                                detected_lang_name=dl_name,
                            )
                        )
                    if new_rows:
                        db.add_all(new_rows)

                    run.api_calls_used = api_calls_used
                    await db.commit()
                    await asyncio.sleep(API_CALL_DELAY_SECONDS)

    run.api_calls_used = api_calls_used
    run.completed_at = datetime.now(timezone.utc)
    if quota_hit:
        run.status = RunStatus.failed
        run.error_message = last_error or "Google CSE quota exceeded."
    else:
        run.status = RunStatus.complete
        run.error_message = last_error  # non-fatal page errors, if any
    await db.commit()
