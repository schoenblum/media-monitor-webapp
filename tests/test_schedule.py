"""Tests for v2.4 item 7 — scheduled / automatic runs.

These exercise the schema validation, the search-config round-trip through the
API, and the scheduler's fire path *without* actually starting APScheduler.
The single-firing advisory lock can only be exercised against a real Postgres
host — the brief's "verify on the host with a short interval" deployer note
covers that final check.
"""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select


async def _login(client):
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "TestAdminPassword!"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_schedule_defaults_to_manual_mode():
    from app.schemas.search import ScheduleConfig, SearchConfig

    s = SearchConfig()
    assert s.schedule.mode == "manual"
    assert s.schedule.interval_hours == 24
    assert s.schedule.start_time == "08:00"
    assert s.schedule.timezone == "Asia/Tokyo"

    # Construct directly too.
    assert ScheduleConfig().mode == "manual"


def test_schedule_round_trip_through_config():
    from app.schemas.search import SearchConfig

    raw = {
        "schedule": {
            "mode": "auto",
            "interval_hours": 6,
            "start_time": "09:30",
            "timezone": "Europe/Berlin",
        },
    }
    s = SearchConfig.model_validate(raw)
    assert s.schedule.mode == "auto"
    assert s.schedule.interval_hours == 6
    assert s.schedule.start_time == "09:30"
    assert s.schedule.timezone == "Europe/Berlin"


def test_invalid_start_time_rejected():
    from pydantic import ValidationError

    from app.schemas.search import ScheduleConfig

    with pytest.raises(ValidationError):
        ScheduleConfig(start_time="bogus")
    with pytest.raises(ValidationError):
        ScheduleConfig(start_time="25:00")  # hour out of range
    with pytest.raises(ValidationError):
        ScheduleConfig(start_time="8:00")  # not zero-padded


def test_invalid_timezone_rejected():
    from pydantic import ValidationError

    from app.schemas.search import ScheduleConfig

    with pytest.raises(ValidationError):
        ScheduleConfig(timezone="Not/AZone")


def test_auto_plus_range_accepted_at_config_level():
    """v2.4.1 — auto + range is now allowed; the engine treats the range as
    a one-time initial backfill on the first scheduled run and switches to
    "last" semantics for subsequent runs (see _resolve_effective_window).
    """
    from app.schemas.search import SearchConfig

    cfg = SearchConfig(
        search_window="range",
        date_from="2026-05-01",
        date_to="2026-05-10",
        schedule={"mode": "auto", "interval_hours": 24, "start_time": "08:00", "timezone": "Asia/Tokyo"},
    )
    assert cfg.schedule.mode == "auto"
    assert cfg.search_window == "range"


def test_interval_hours_must_be_positive():
    from pydantic import ValidationError

    from app.schemas.search import ScheduleConfig

    with pytest.raises(ValidationError):
        ScheduleConfig(interval_hours=0)


# ---------------------------------------------------------------------------
# End-to-end via the searches API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_update_accepts_schedule_block(client):
    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    sid = r.json()[0]["id"]

    body = {
        "config": {
            "search_window": "last",
            "fallback_hours": 72,
            "date_from": "",
            "date_to": "",
            "terms_pages": 1,
            "terms": [{"id": "t1", "text": "kobe", "operator": None}],
            "doi": {"text": "", "pages": 1},
            "university_name": {"enabled": False, "language_ids": [], "pages": 1},
            "outlets": {"enabled": False, "outlet_ids": []},
            "schedule": {
                "mode": "auto",
                "interval_hours": 12,
                "start_time": "07:15",
                "timezone": "America/New_York",
            },
        },
    }
    upd = await client.put(f"/api/v1/searches/{sid}", json=body, headers=h)
    assert upd.status_code == 200, upd.text
    persisted = upd.json()["config"]["schedule"]
    assert persisted["mode"] == "auto"
    assert persisted["interval_hours"] == 12
    assert persisted["start_time"] == "07:15"
    assert persisted["timezone"] == "America/New_York"


@pytest.mark.asyncio
async def test_search_update_accepts_auto_plus_range(client):
    """v2.4.1 — auto + range is allowed via the PUT endpoint."""
    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    sid = r.json()[0]["id"]

    body = {
        "config": {
            "search_window": "range",
            "fallback_hours": 72,
            "date_from": "2026-05-01",
            "date_to": "2026-05-10",
            "terms_pages": 1,
            "terms": [{"id": "t1", "text": "kobe", "operator": None}],
            "doi": {"text": "", "pages": 1},
            "university_name": {"enabled": False, "language_ids": [], "pages": 1},
            "outlets": {"enabled": False, "outlet_ids": []},
            "schedule": {
                "mode": "auto",
                "interval_hours": 24,
                "start_time": "08:00",
                "timezone": "Asia/Tokyo",
            },
        },
    }
    upd = await client.put(f"/api/v1/searches/{sid}", json=body, headers=h)
    assert upd.status_code == 200, upd.text
    persisted = upd.json()["config"]
    assert persisted["search_window"] == "range"
    assert persisted["schedule"]["mode"] == "auto"
    assert persisted["date_from"] == "2026-05-01"


# ---------------------------------------------------------------------------
# Auto+range effective-window semantics (v2.4.1 feature change)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auto_range_first_run_uses_range(client, session_factory):
    """First scheduled fire of an auto+range search keeps the date range —
    it's the initial backfill the user explicitly asked for.
    """
    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.user import User
    from app.services.search_engine import _resolve_effective_window

    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    sid = UUID(r.json()[0]["id"])

    config = {
        "search_window": "range",
        "date_from": "2026-05-01",
        "date_to": "2026-05-10",
        "schedule": {"mode": "auto", "interval_hours": 24, "start_time": "08:00", "timezone": "Asia/Tokyo"},
    }

    async with session_factory() as db:
        admin = (
            await db.execute(select(User).where(User.email == "admin@example.com"))
        ).scalar_one()
        # The current run is freshly inserted; no prior completed runs of this
        # search exist → effective window stays "range".
        current = Run(
            id=uuid4(),
            user_id=admin.id,
            search_id=sid,
            triggered_by=RunTrigger.scheduled,
            status=RunStatus.running,
        )
        db.add(current)
        await db.commit()
        await db.refresh(current)
        effective = await _resolve_effective_window(db, current, config)

    assert effective["search_window"] == "range"
    assert effective["date_from"] == "2026-05-01"


@pytest.mark.asyncio
async def test_auto_range_subsequent_run_flips_to_last(client, session_factory):
    """Once a prior completed run of an auto+range search exists, the
    effective window flips to "last" — only what's new since last fire.
    """
    from datetime import timedelta

    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.user import User
    from app.services.search_engine import _resolve_effective_window

    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    sid = UUID(r.json()[0]["id"])

    config = {
        "search_window": "range",
        "date_from": "2026-05-01",
        "date_to": "2026-05-10",
        "schedule": {"mode": "auto", "interval_hours": 24, "start_time": "08:00", "timezone": "Asia/Tokyo"},
    }

    async with session_factory() as db:
        admin = (
            await db.execute(select(User).where(User.email == "admin@example.com"))
        ).scalar_one()
        now = datetime.now(timezone.utc)
        prior = Run(
            id=uuid4(),
            user_id=admin.id,
            search_id=sid,
            triggered_by=RunTrigger.scheduled,
            status=RunStatus.complete,
            started_at=now - timedelta(hours=24),
            completed_at=now - timedelta(hours=24),
        )
        current = Run(
            id=uuid4(),
            user_id=admin.id,
            search_id=sid,
            triggered_by=RunTrigger.scheduled,
            status=RunStatus.running,
        )
        db.add_all([prior, current])
        await db.commit()
        await db.refresh(current)
        effective = await _resolve_effective_window(db, current, config)

    assert effective["search_window"] == "last"
    # The literal range fields are preserved on the dict (we only override
    # the window) so nothing else in the config drifts.
    assert effective["date_from"] == "2026-05-01"


@pytest.mark.asyncio
async def test_manual_range_run_keeps_literal_range(client, session_factory):
    """Manual / webhook range runs are NOT affected by the new override —
    the user is explicitly asking for that exact window every time.
    """
    from datetime import timedelta

    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.user import User
    from app.services.search_engine import _resolve_effective_window

    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    sid = UUID(r.json()[0]["id"])

    config = {
        "search_window": "range",
        "date_from": "2026-05-01",
        "date_to": "2026-05-10",
        "schedule": {"mode": "manual", "interval_hours": 24, "start_time": "08:00", "timezone": "Asia/Tokyo"},
    }

    async with session_factory() as db:
        admin = (
            await db.execute(select(User).where(User.email == "admin@example.com"))
        ).scalar_one()
        now = datetime.now(timezone.utc)
        # Even with a prior completed run, a manual range run stays "range".
        prior = Run(
            id=uuid4(),
            user_id=admin.id,
            search_id=sid,
            triggered_by=RunTrigger.manual,
            status=RunStatus.complete,
            started_at=now - timedelta(hours=24),
            completed_at=now - timedelta(hours=24),
        )
        current = Run(
            id=uuid4(),
            user_id=admin.id,
            search_id=sid,
            triggered_by=RunTrigger.manual,
            status=RunStatus.running,
        )
        db.add_all([prior, current])
        await db.commit()
        await db.refresh(current)
        effective = await _resolve_effective_window(db, current, config)

    assert effective["search_window"] == "range"


# ---------------------------------------------------------------------------
# Fire path — directly exercise scheduler.fire_search without booting APScheduler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fire_search_records_skipped_when_no_credentials(client, session_factory):
    """An ineligible scheduled fire produces a visible Skipped run, not silence
    (decision A in the v2.4 brief).
    """
    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.user import User
    from app.services.scheduler import fire_search

    h = await _login(client)
    r = await client.get("/api/v1/searches", headers=h)
    sid = UUID(r.json()[0]["id"])

    # Bootstrap admin has no Google credentials → fire_search should skip.
    await fire_search(sid)

    async with session_factory() as db:
        runs = (
            await db.execute(
                select(Run)
                .where(Run.search_id == sid)
                .order_by(Run.started_at.desc())
            )
        ).scalars().all()
    assert runs, "fire_search should record a Run even on skip"
    skipped = runs[0]
    assert skipped.triggered_by == RunTrigger.scheduled
    assert skipped.status == RunStatus.skipped
    assert skipped.error_message and "credentials" in skipped.error_message.lower()
    assert skipped.completed_at is not None


@pytest.mark.asyncio
async def test_fire_search_records_skipped_when_config_invalid(client, session_factory):
    """A scheduled fire on a config with no terms/DOI/university_name records
    a Skipped run with a clear reason.
    """
    from app.models.run import Run, RunStatus, RunTrigger
    from app.models.search import Search
    from app.models.user import User
    from app.services.scheduler import fire_search

    h = await _login(client)
    # Give the bootstrap admin fake-but-present credentials so the credential
    # guard passes and we exercise the validate_search_config branch.
    async with session_factory() as db:
        admin = (
            await db.execute(select(User).where(User.email == "admin@example.com"))
        ).scalar_one()
        admin.google_api_key_encrypted = b"fake-encrypted-key"
        admin.search_engine_id_encrypted = b"fake-encrypted-cx"
        # Empty out the seeded search so validate_search_config returns False.
        empty_search = Search(
            user_id=admin.id,
            name="Empty",
            is_default=False,
            config={
                "search_window": "last",
                "fallback_hours": 72,
                "date_from": "",
                "date_to": "",
                "terms_pages": 1,
                "terms": [],
                "doi": {"text": "", "pages": 1},
                "university_name": {"enabled": False, "language_ids": [], "pages": 1},
                "outlets": {"enabled": False, "outlet_ids": []},
                "schedule": {"mode": "auto", "interval_hours": 24, "start_time": "08:00", "timezone": "Asia/Tokyo"},
            },
        )
        db.add(empty_search)
        await db.commit()
        await db.refresh(empty_search)
        sid = empty_search.id

    await fire_search(sid)

    async with session_factory() as db:
        runs = (
            await db.execute(select(Run).where(Run.search_id == sid))
        ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == RunStatus.skipped
    assert runs[0].triggered_by == RunTrigger.scheduled
    assert runs[0].error_message and "config" in runs[0].error_message.lower()


def test_next_fire_time_advances_when_anchor_past():
    """The interval anchor walks forward by interval_hours until in the future."""
    from app.services.scheduler import _next_fire_time

    # Daily at 08:00 Asia/Tokyo: the next fire is always today or tomorrow at 08:00 JST.
    next_fire = _next_fire_time("08:00", "Asia/Tokyo", 24)
    assert next_fire.tzinfo is not None
    assert next_fire > datetime.now(timezone.utc)
    # And it's within roughly a day.
    assert next_fire - datetime.now(timezone.utc) <= timedelta(hours=25)


def test_stable_lock_key_is_deterministic_and_in_range():
    from app.services.scheduler import _stable_lock_key

    assert _stable_lock_key("a") == _stable_lock_key("a")
    assert _stable_lock_key("a") != _stable_lock_key("b")
    k = _stable_lock_key("mm-scheduler:something")
    assert 0 <= k < 2**31
