"""Tests for the run lifecycle — date extractor, run trigger guard, CSV export."""
import csv
import io
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.services.date_extractor import extract_date


async def _login(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "TestAdminPassword!"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_date_extractor_handles_common_formats():
    assert extract_date("Published 12 March 2026 by …") == "2026/03/12"
    assert extract_date("March 12, 2026 — story") == "2026/03/12"
    assert extract_date("2026-03-12 byline") == "2026/03/12"
    assert extract_date("2026/03/12 17:00") == "2026/03/12"
    assert extract_date("no date here") == ""
    assert extract_date("") == ""


@pytest.mark.asyncio
async def test_trigger_run_requires_credentials(client):
    h = await _login(client)
    # Find the seeded default search.
    searches = (await client.get("/api/v1/searches", headers=h)).json()
    default = next(s for s in searches if s["is_default"])

    r = await client.post(
        "/api/v1/runs", json={"search_id": default["id"]}, headers=h
    )
    assert r.status_code == 400
    assert "credentials" in r.json()["detail"].lower()


def test_search_engine_never_writes_legacy_web_outlet_name():
    """Guard for the v2.4 item 2 invariant.

    Pre-v2.2, bare (no site:) searches stored ``outlet_name = "Web"`` on each
    Result row. v2.2 switched the sentinel to ``""`` and v2.4 migration 0007
    backfilled the historical rows. This test documents that the engine source
    no longer mentions the legacy literal anywhere, so the dataset stays
    consistent without a second renaming round.
    """
    src = Path("app/services/search_engine.py").read_text(encoding="utf-8")
    assert '"Web"' not in src and "'Web'" not in src, (
        "search_engine.py must not write the legacy 'Web' outlet_name sentinel — "
        "use '' (empty string) instead and let the UI derive the host from the URL."
    )


@pytest.mark.asyncio
async def test_dedupe_collects_urls_from_prior_runs_in_window(client, session_factory):
    """Item 4b — _collect_recent_seen_urls covers prior completed runs within
    DEDUPE_WINDOW_DAYS of the previous run, and ignores older / non-complete ones."""
    from app.models.result import Result
    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.search import Search
    from app.models.user import User
    from app.services.search_engine import DEDUPE_WINDOW_DAYS, _collect_recent_seen_urls
    from sqlalchemy import select

    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    search_id = UUID(r.json()[0]["id"])

    async with session_factory() as db:
        user = (
            await db.execute(select(User).where(User.email == "admin@example.com"))
        ).scalar_one()

        now = datetime.now(timezone.utc)
        prev = Run(
            id=uuid4(),
            user_id=user.id,
            search_id=search_id,
            triggered_by=RunTrigger.manual,
            status=RunStatus.complete,
            started_at=now - timedelta(hours=12),
            completed_at=now - timedelta(hours=12),
        )
        old = Run(  # well outside the 2-day window from prev
            id=uuid4(),
            user_id=user.id,
            search_id=search_id,
            triggered_by=RunTrigger.manual,
            status=RunStatus.complete,
            started_at=now - timedelta(days=DEDUPE_WINDOW_DAYS + 5),
            completed_at=now - timedelta(days=DEDUPE_WINDOW_DAYS + 5),
        )
        in_window_failed = Run(  # in window but failed → excluded
            id=uuid4(),
            user_id=user.id,
            search_id=search_id,
            triggered_by=RunTrigger.manual,
            status=RunStatus.failed,
            started_at=now - timedelta(hours=18),
        )
        current = Run(
            id=uuid4(),
            user_id=user.id,
            search_id=search_id,
            triggered_by=RunTrigger.manual,
            status=RunStatus.running,
            started_at=now,
        )
        db.add_all([prev, old, in_window_failed, current])
        await db.flush()
        db.add_all([
            Result(
                run_id=prev.id, outlet_name="", title="t", url="https://a.test/x",
                display_source="", snippet="", date_extracted="",
                keyword_used="", search_lang="", detected_lang="", detected_lang_name="",
            ),
            Result(
                run_id=prev.id, outlet_name="", title="t", url="https://b.test/y",
                display_source="", snippet="", date_extracted="",
                keyword_used="", search_lang="", detected_lang="", detected_lang_name="",
            ),
            Result(
                run_id=old.id, outlet_name="", title="t", url="https://old.test/z",
                display_source="", snippet="", date_extracted="",
                keyword_used="", search_lang="", detected_lang="", detected_lang_name="",
            ),
            Result(
                run_id=in_window_failed.id, outlet_name="", title="t",
                url="https://failed.test/f",
                display_source="", snippet="", date_extracted="",
                keyword_used="", search_lang="", detected_lang="", detected_lang_name="",
            ),
        ])
        await db.commit()

        seen = await _collect_recent_seen_urls(db, search_id, current.id)

    assert "https://a.test/x" in seen
    assert "https://b.test/y" in seen
    assert "https://old.test/z" not in seen
    assert "https://failed.test/f" not in seen


@pytest.mark.asyncio
async def test_dedupe_no_prior_runs_returns_empty(client, session_factory):
    """First run of a search has no anchor → nothing to dedupe against."""
    from app.services.search_engine import _collect_recent_seen_urls

    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    search_id = UUID(r.json()[0]["id"])

    async with session_factory() as db:
        seen = await _collect_recent_seen_urls(db, search_id, uuid4())
    assert seen == set()


@pytest.mark.asyncio
async def test_run_create_accepts_deduplicate_flag(client):
    """The trigger endpoint accepts (and defaults) the per-run deduplicate flag.

    It still errors on credentials (the standard pre-flight) — the point of this
    test is the schema, not the run itself.
    """
    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    search_id = next(s for s in r.json() if s["is_default"])["id"]

    # Default (no key): payload accepted by schema, blocked by credentials guard.
    r1 = await client.post(
        "/api/v1/runs", json={"search_id": search_id}, headers=h
    )
    assert r1.status_code == 400
    # Explicit deduplicate=False: same schema, same guard.
    r2 = await client.post(
        "/api/v1/runs",
        json={"search_id": search_id, "deduplicate": False},
        headers=h,
    )
    assert r2.status_code == 400


@pytest.mark.asyncio
async def test_csv_export_empty_runs(client):
    """Hits a clean error when run_ids do not belong to the user — sanity check."""
    h = await _login(client)
    r = await client.get(
        "/api/v1/runs/export?run_ids[]=00000000-0000-0000-0000-000000000000",
        headers=h,
    )
    assert r.status_code == 403
