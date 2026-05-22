"""Core search-engine logic — config-based query builder.

Each Run calls ``execute_run`` in the background:

1. Loads the Search's config JSON and the user's encrypted Google credentials.
2. Resolves outlet and university-language records referenced in the config.
3. Builds a list of (query_string, pages, applicable_outlets) tuples.
4. Executes paginated Google CSE requests and deduplicates by URL.
5. Commits Result rows as they arrive; marks the Run complete/failed on exit.

Query composition rules (revision v2.2):

* **DOI** is always its own standalone query, unaffected by terms and operators,
  with its own ``doi.pages`` page count.
* **Terms** are concatenated (AND/OR/NOT) into a single combined query.
* When **university_name is enabled** with N selected languages, the terms
  query is *replaced* by N per-language queries of the form
  ``(combined_terms) AND "<university_name_in_lang_N>"`` (or just
  ``"<university_name_in_lang_N>"`` when there are no terms).
  Each such query fetches ``university_name.pages`` pages.
* When **university_name is disabled**, the combined terms query (if any) runs
  on its own, fetching ``terms_pages`` pages.
"""
import asyncio
import logging
from datetime import date, datetime, timezone
from math import ceil
from typing import NamedTuple
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.models.language import UniversityLanguage
from app.models.outlet import Outlet
from app.models.result import Result
from app.models.run import Run, RunStatus
from app.models.search import Search
from app.models.user import User
from app.services.crypto import decrypt
from app.services.date_extractor import extract_date
from app.services.default_outlets import EXCLUDED_DOMAINS
from app.services.lang_detector import detect_language


logger = logging.getLogger(__name__)

GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
API_CALL_DELAY_SECONDS = 0.5
DEFAULT_LOOKBACK_HOURS = 72
MAX_PAGES = 10


class QuerySpec(NamedTuple):
    query: str
    pages: int
    outlets: list  # list of Outlet objects; empty = no site restriction
    iso_code: str  # language ISO for outlet-language filtering; "" = no language axis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalise_domain(domain: str) -> str:
    d = domain.strip().lower()
    for prefix in ("https://", "http://", "site:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/")


def _is_excluded_url(url: str) -> bool:
    url_lower = url.lower()
    return any(d in url_lower for d in EXCLUDED_DOMAINS)


def _build_term_query(terms: list[dict]) -> str | None:
    """Combine term rows into a single Google query string using Google boolean syntax."""
    parts: list[str] = []
    for term in terms:
        text = term.get("text", "").strip()
        if not text:
            continue
        quoted = f'"{text}"'
        if not parts:
            parts.append(quoted)
        else:
            op = (term.get("operator") or "AND").upper()
            if op == "OR":
                parts.append(f"OR {quoted}")
            elif op == "NOT":
                parts.append(f"-{quoted}")
            else:  # AND — adjacent quoted phrases are AND in Google
                parts.append(quoted)
    return " ".join(parts) if parts else None


def _build_query_specs(
    config: dict,
    all_outlets: list,
    languages: dict,
) -> list[QuerySpec]:
    """Convert a search config dict into a list of QuerySpec to execute."""
    specs: list[QuerySpec] = []

    terms = config.get("terms", [])
    doi_cfg = config.get("doi", {})
    uni_cfg = config.get("university_name", {})
    outlets_cfg = config.get("outlets", {})

    # Resolve outlets
    outlets_enabled = outlets_cfg.get("enabled", False)
    outlet_id_set = set(str(oid) for oid in outlets_cfg.get("outlet_ids", []))
    active_outlets = (
        [o for o in all_outlets if str(o.id) in outlet_id_set and o.is_active]
        if outlets_enabled
        else []
    )

    base_query = _build_term_query(terms)
    terms_pages = int(config.get("terms_pages") or 1)

    # DOI — always standalone.
    doi_text = doi_cfg.get("text", "").strip()
    doi_pages = int(doi_cfg.get("pages") or 1)
    if doi_text:
        specs.append(
            QuerySpec(
                query=f'"{doi_text}"',
                pages=doi_pages,
                outlets=list(active_outlets) if outlets_enabled else [],
                iso_code="",
            )
        )

    # University name — AND constraint on the terms, one query per active language.
    uni_enabled = uni_cfg.get("enabled", False)
    uni_lang_ids = [str(lid) for lid in uni_cfg.get("language_ids", [])]
    uni_pages = int(uni_cfg.get("pages") or 1)

    if uni_enabled and uni_lang_ids:
        for lang_id in uni_lang_ids:
            lang = languages.get(lang_id)
            if not lang:
                continue
            iso = lang.iso_code
            uni_name = lang.university_name
            if base_query:
                q = f'{base_query} "{uni_name}"'
            else:
                q = f'"{uni_name}"'
            specs.append(
                QuerySpec(
                    query=q,
                    pages=uni_pages,
                    outlets=list(active_outlets) if outlets_enabled else [],
                    iso_code=iso,
                )
            )
    elif base_query:
        # Plain terms query without the university-name constraint.
        specs.append(
            QuerySpec(
                query=base_query,
                pages=terms_pages,
                outlets=list(active_outlets) if outlets_enabled else [],
                iso_code="",
            )
        )

    return specs


def _filter_outlets_by_lang(outlets: list, iso_code: str) -> list:
    """Return outlets that have no language restriction or include this ISO code.

    Called only for queries that have a language axis (university-name queries).
    For DOI and plain-terms queries (iso_code == ""), no filtering is applied.
    """
    if not iso_code:
        return outlets
    return [o for o in outlets if not o.keyword_langs or iso_code in o.keyword_langs]


# ---------------------------------------------------------------------------
# Date-window helpers
# ---------------------------------------------------------------------------


def _build_date_params(config: dict, lookback_days: int) -> dict:
    """Return Google CSE date-restriction query params for this config.

    For "last" / "hours" windows we use ``dateRestrict=d{n}``. For the explicit
    "range" window we use ``sort=date:r:YYYYMMDD:YYYYMMDD`` with ``date_to``
    defaulting to today when omitted.
    """
    if config.get("search_window") == "range":
        df_raw = (config.get("date_from") or "").strip()
        dt_raw = (config.get("date_to") or "").strip()
        try:
            df = date.fromisoformat(df_raw) if df_raw else None
        except ValueError:
            df = None
        if df is None:
            # Schema validation should prevent this; fall back to a relative window.
            return {"dateRestrict": f"d{max(1, lookback_days)}"}
        try:
            dt = date.fromisoformat(dt_raw) if dt_raw else date.today()
        except ValueError:
            dt = date.today()
        return {"sort": f"date:r:{df.strftime('%Y%m%d')}:{dt.strftime('%Y%m%d')}"}
    return {"dateRestrict": f"d{max(1, lookback_days)}"}


async def _compute_lookback(
    db: AsyncSession, search_id: UUID, current_run_id: UUID, config: dict
) -> int:
    """Return the lookback window in days for relative search windows."""
    from app.models.run import RunStatus as RS

    search_window = config.get("search_window", "last")
    fallback_hours = int(config.get("fallback_hours", DEFAULT_LOOKBACK_HOURS))

    if search_window == "hours":
        return max(1, ceil(fallback_hours / 24))

    # Explicit date ranges do not need a lookback; the caller will pick the
    # sort= param. Returning fallback as a no-op default keeps the contract simple.
    if search_window == "range":
        return max(1, ceil(fallback_hours / 24))

    # "last" — find most recent prior completed run for this search
    stmt = (
        select(Run.started_at)
        .where(Run.search_id == search_id)
        .where(Run.id != current_run_id)
        .where(Run.status == RS.complete)
        .order_by(Run.started_at.desc())
        .limit(1)
    )
    prev_started: datetime | None = (await db.execute(stmt)).scalar_one_or_none()
    if prev_started is None:
        return max(1, ceil(fallback_hours / 24))
    now = datetime.now(timezone.utc)
    if prev_started.tzinfo is None:
        prev_started = prev_started.replace(tzinfo=timezone.utc)
    return max(1, (now - prev_started).days + 1)


async def _fetch_page(
    client: httpx.AsyncClient,
    api_key: str,
    engine_id: str,
    query: str,
    start: int,
    date_params: dict,
) -> tuple[list[dict], bool, str | None]:
    params = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": 10,
        "start": start,
        **date_params,
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def execute_run(run_id: UUID) -> None:
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

    search = (
        await db.execute(select(Search).where(Search.id == run.search_id))
    ).scalar_one_or_none()
    if search is None:
        await _mark_failed(db, run_id, "Search not found")
        return

    user = await db.get(User, run.user_id)
    if user is None:
        await _mark_failed(db, run_id, "User not found")
        return

    if not user.google_api_key_encrypted or not user.search_engine_id_encrypted:
        await _mark_failed(db, run_id, "Google API credentials not configured. Add them in Settings.")
        return

    try:
        api_key = decrypt(user.google_api_key_encrypted)
        engine_id = decrypt(user.search_engine_id_encrypted)
    except Exception as exc:  # noqa: BLE001
        await _mark_failed(db, run_id, f"Failed to decrypt API credentials: {exc}")
        return

    config = search.config or {}

    # Validate that there is something to search for
    from app.routers.searches import validate_search_config
    if not validate_search_config(config):
        await _mark_failed(
            db,
            run_id,
            "Search has no active terms, DOI, or university name — nothing to search for.",
        )
        return

    # Load all user outlets
    all_outlets = (
        await db.execute(select(Outlet).where(Outlet.user_id == run.user_id))
    ).scalars().all()

    # Load user's university languages
    lang_rows = (
        await db.execute(
            select(UniversityLanguage).where(UniversityLanguage.user_id == run.user_id)
        )
    ).scalars().all()
    languages = {str(lang.id): lang for lang in lang_rows}

    days = await _compute_lookback(db, search.id, run.id, config)
    date_params = _build_date_params(config, days)
    specs = _build_query_specs(config, list(all_outlets), languages)

    if not specs:
        run.status = RunStatus.complete
        run.completed_at = datetime.now(timezone.utc)
        run.error_message = "No queries could be built from the search configuration."
        await db.commit()
        return

    seen_urls: set[str] = set()
    api_calls_used = 0
    quota_hit = False
    last_error: str | None = None

    async with httpx.AsyncClient() as client:
        for spec in specs:
            if quota_hit:
                break

            pages = max(1, min(MAX_PAGES, spec.pages))
            applicable_outlets = _filter_outlets_by_lang(spec.outlets, spec.iso_code)

            if applicable_outlets:
                # Run the query against each outlet domain
                for outlet in applicable_outlets:
                    if quota_hit:
                        break
                    domain = _normalise_domain(outlet.domain)
                    full_query = f"{spec.query} site:{domain}"
                    for page in range(pages):
                        start = page * 10 + 1
                        items, quota, err = await _fetch_page(
                            client, api_key, engine_id, full_query, start, date_params
                        )
                        api_calls_used += 1

                        if quota:
                            quota_hit = True
                            last_error = err
                            break
                        if err:
                            last_error = err
                            logger.warning(
                                "Query '%s' outlet=%s page=%d: %s",
                                spec.query[:60], outlet.name, page + 1, err,
                            )
                            break
                        if not items:
                            break

                        new_rows = _make_result_rows(
                            items, run.id, outlet.name, spec.query, seen_urls
                        )
                        if new_rows:
                            db.add_all(new_rows)

                        run.api_calls_used = api_calls_used
                        await db.commit()
                        await asyncio.sleep(API_CALL_DELAY_SECONDS)
            else:
                # Bare search without site: restriction
                for page in range(pages):
                    if quota_hit:
                        break
                    start = page * 10 + 1
                    items, quota, err = await _fetch_page(
                        client, api_key, engine_id, spec.query, start, date_params
                    )
                    api_calls_used += 1

                    if quota:
                        quota_hit = True
                        last_error = err
                        break
                    if err:
                        last_error = err
                        logger.warning("Query '%s' page=%d: %s", spec.query[:60], page + 1, err)
                        break
                    if not items:
                        break

                    new_rows = _make_result_rows(
                        items, run.id, "", spec.query, seen_urls
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
        run.error_message = last_error
    await db.commit()


def _make_result_rows(
    items: list[dict],
    run_id: UUID,
    outlet_name: str,
    keyword_used: str,
    seen_urls: set[str],
) -> list[Result]:
    rows: list[Result] = []
    for item in items:
        url = item.get("link", "")
        if not url or url in seen_urls:
            continue
        if _is_excluded_url(url):
            continue
        seen_urls.add(url)
        title = item.get("title", "No title")
        snippet = item.get("snippet", "") or ""
        dl_code, dl_name = detect_language(title, snippet)
        rows.append(
            Result(
                run_id=run_id,
                outlet_name=outlet_name,
                title=title,
                url=url,
                display_source=item.get("displayLink", "") or "",
                snippet=snippet,
                date_extracted=extract_date(snippet),
                keyword_used=keyword_used[:255],
                search_lang="",
                detected_lang=dl_code,
                detected_lang_name=dl_name,
            )
        )
    return rows
