"""In-process APScheduler runtime for the v2.4 item 7 "automatic runs" feature.

Architecture (mirrors HANDOVER §8 — keep that section in sync if anything
here changes):

* The scheduler is an ``AsyncIOScheduler`` started from FastAPI's lifespan
  (``app/main.py``). There is no separate systemd service.
* ``media-monitor.service`` runs **two Uvicorn workers** in production. Each
  worker boots its own scheduler instance and both register the same jobs
  from the database. Without a guard this would double-fire every job.
  Single-firing is enforced with a **per-fire Postgres advisory lock**: the
  fire function tries ``pg_try_advisory_xact_lock`` keyed on
  ``(search_id, fire_minute)``; the loser exits before touching the DB and
  the winner creates the run. Transaction-scoped (xact) means the lock
  auto-releases on commit, so we never have to track held locks.
* Each ``Search`` with ``config.schedule.mode == "auto"`` becomes one
  APScheduler ``IntervalTrigger`` job, with the first fire computed from
  ``start_time`` + ``timezone`` and subsequent fires every
  ``interval_hours`` from that anchor.
* The user-facing source of truth is ``Search.config.schedule``. APScheduler's
  internal jobs are derived state — rebuilt on startup and on every search
  mutation. The two must never drift; ``reconcile_jobs()`` is the only path
  that adds, modifies, or removes scheduler jobs.

On SQLite (tests) the advisory-lock primitive is unavailable, so the lock
helper degrades to "always grant". The test suite covers the fire path
directly without booting a scheduler.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal, engine
from app.models.run import Run, RunStatus, RunTrigger
from app.models.search import Search
from app.models.user import User


logger = logging.getLogger(__name__)


_scheduler: Optional["AsyncIOScheduler"] = None  # type: ignore[name-defined]


JOB_PREFIX = "mm-search:"


def _job_id_for(search_id: UUID | str) -> str:
    return f"{JOB_PREFIX}{search_id}"


def _stable_lock_key(payload: str) -> int:
    """Map an arbitrary string to a 31-bit signed int for pg_advisory_lock.

    Advisory lock keys are bigint, but using a 31-bit value keeps the result
    well clear of any other application-level keys and avoids accidental
    collisions with subsystems that happen to pass small integers.
    """
    h = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big", signed=False) & 0x7FFFFFFF


async def _try_acquire_fire_lock(
    db: AsyncSession, search_id: UUID, fire_minute: datetime
) -> bool:
    """Try to claim this (search, minute) for the current worker.

    On non-Postgres backends (the SQLite test suite) advisory locks don't
    exist; we assume single-firing because the test suite never starts the
    scheduler. In production both Uvicorn workers will reach this point at
    virtually the same instant — only one wins the xact lock.
    """
    if engine.dialect.name != "postgresql":
        return True
    key = _stable_lock_key(f"mm-scheduler:{search_id}:{fire_minute.isoformat()}")
    result = await db.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": key})
    got = result.scalar()
    return bool(got)


async def _record_skipped_run(
    db: AsyncSession, search: Search, user: User | None, reason: str
) -> Run:
    """Record a visible Skipped run when a scheduled fire can't proceed.

    Per decision A in the v2.4 brief, ineligibility produces a discoverable
    Run row (status=skipped, error_message=<reason>) instead of a silent
    no-op — otherwise a forgotten recurring search that has run out of
    Google credits produces nothing the user can see in Run History.
    """
    run = Run(
        user_id=user.id if user else search.user_id,
        search_id=search.id,
        university_id=user.university_id if user else None,
        triggered_by=RunTrigger.scheduled,
        status=RunStatus.skipped,
        error_message=reason[:1900],
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def fire_search(search_id: UUID | str) -> None:
    """APScheduler entry point — fire one scheduled run of ``search_id``.

    Idempotent across workers via the per-fire advisory lock. Reuses
    ``execute_run`` so scheduled runs behave identically to manual/webhook
    ones (including the v2.4 item 4b cross-run dedupe, which we always
    enable for scheduled fires because recurring jobs are exactly the case
    that benefits from it).
    """
    # Late import: app.services.search_engine pulls in httpx etc. that the
    # scheduler module doesn't otherwise need at import time.
    from app.routers.searches import validate_search_config
    from app.services.search_engine import execute_run

    sid = UUID(str(search_id)) if not isinstance(search_id, UUID) else search_id
    fire_minute = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    run_id_to_execute: UUID | None = None
    async with SessionLocal() as db:
        if not await _try_acquire_fire_lock(db, sid, fire_minute):
            logger.info("Search %s: another worker claimed this fire — skipping", sid)
            return

        search = await db.get(Search, sid)
        if search is None:
            logger.warning("Scheduled fire for missing search %s — removing job", sid)
            await remove_search_job(sid)
            return

        user = await db.get(User, search.user_id)
        if user is None or not user.is_active:
            await _record_skipped_run(db, search, user, "Skipped: owner account inactive")
            return

        if not user.google_api_key_encrypted or not user.search_engine_id_encrypted:
            await _record_skipped_run(
                db, search, user, "Skipped: no Google credentials configured"
            )
            return

        if not validate_search_config(search.config or {}):
            await _record_skipped_run(
                db,
                search,
                user,
                "Skipped: search config has no terms, DOI, or university name",
            )
            return

        run = Run(
            user_id=user.id,
            search_id=search.id,
            # Snapshot affiliation at run-creation time, same rule as manual
            # and webhook triggers (revision_brief_v2.2.md §8.3).
            university_id=user.university_id,
            triggered_by=RunTrigger.scheduled,
            status=RunStatus.pending,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id_to_execute = run.id

    if run_id_to_execute is not None:
        # Fire-and-forget: execute_run opens its own session and pages CSE
        # results in the background. We do NOT await it here because the
        # scheduler thread should return promptly.
        asyncio.create_task(execute_run(run_id_to_execute, deduplicate=True))


# ---------------------------------------------------------------------------
# Job (re)registration
# ---------------------------------------------------------------------------


def _schedule_config(search: Search) -> dict | None:
    cfg = (search.config or {}).get("schedule") or {}
    if cfg.get("mode") != "auto":
        return None
    return cfg


def _next_fire_time(start_time: str, tz_name: str, interval_hours: int) -> datetime:
    """Return the next UTC datetime that aligns to ``start_time`` in ``tz_name``.

    For daily / weekly cadences this is just "the next occurrence of HH:MM in
    the given zone". For sub-daily intervals (interval_hours < 24) we anchor
    the cadence to the start time and step forward until we land in the
    future — so "every 6h starting 08:00" fires at 08:00, 14:00, 20:00, 02:00
    in the local zone rather than at arbitrary fractional offsets.
    """
    zone = ZoneInfo(tz_name)
    now_local = datetime.now(zone)
    hh, mm = (int(x) for x in start_time.split(":"))
    anchor = now_local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if anchor <= now_local:
        # Walk forward in interval_hours steps until anchor is in the future.
        delta = timedelta(hours=interval_hours)
        # max() guards against silly inputs (e.g. interval larger than a year).
        steps = max(1, int(((now_local - anchor).total_seconds() // delta.total_seconds())) + 1)
        anchor += delta * steps
    return anchor.astimezone(timezone.utc)


async def register_search_job(search: Search) -> None:
    """Add or replace the APScheduler job for one search.

    No-op if the search is not in auto mode or if the scheduler has not been
    started yet (we'll pick the job up on the next ``reconcile_jobs``).
    """
    if _scheduler is None:
        return
    cfg = _schedule_config(search)
    if cfg is None:
        await remove_search_job(search.id)
        return

    from apscheduler.triggers.interval import IntervalTrigger

    try:
        next_fire = _next_fire_time(
            cfg["start_time"], cfg["timezone"], int(cfg["interval_hours"])
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Search %s has invalid schedule (%s) — not registering", search.id, exc
        )
        await remove_search_job(search.id)
        return

    trigger = IntervalTrigger(
        hours=int(cfg["interval_hours"]),
        start_date=next_fire,
        timezone=timezone.utc,
    )
    _scheduler.add_job(
        fire_search,
        trigger=trigger,
        args=[str(search.id)],
        id=_job_id_for(search.id),
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=300,
    )
    logger.info(
        "Registered scheduled search %s: every %sh from %s",
        search.id, cfg["interval_hours"], next_fire.isoformat(),
    )


async def remove_search_job(search_id: UUID | str) -> None:
    if _scheduler is None:
        return
    try:
        _scheduler.remove_job(_job_id_for(search_id))
    except Exception:
        # Not registered — fine.
        pass


async def reconcile_jobs() -> None:
    """Sync APScheduler jobs to the current set of auto-mode searches.

    Called on startup and after any search mutation that could affect the
    schedule. Search.config.schedule is the source of truth — APScheduler's
    persistent jobstore is derived state.
    """
    if _scheduler is None:
        return
    async with SessionLocal() as db:
        rows = (await db.execute(select(Search))).scalars().all()

    wanted: set[str] = set()
    for s in rows:
        if _schedule_config(s) is None:
            continue
        wanted.add(_job_id_for(s.id))
        await register_search_job(s)

    # Drop jobs whose underlying search vanished or flipped back to manual.
    for job in list(_scheduler.get_jobs()):
        if job.id.startswith(JOB_PREFIX) and job.id not in wanted:
            _scheduler.remove_job(job.id)
            logger.info("Removed scheduled job %s (no longer auto)", job.id)


# ---------------------------------------------------------------------------
# Lifespan integration
# ---------------------------------------------------------------------------


async def start_scheduler() -> None:
    """Start the in-process scheduler. Safe to call once per worker."""
    global _scheduler
    if _scheduler is not None:
        return

    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from app.config import get_settings

    settings = get_settings()
    # APScheduler's SQLAlchemyJobStore wants a *sync* URL; the app uses an
    # async driver. Translate "postgresql+asyncpg://..." → "postgresql://..."
    # so the jobstore can use the psycopg2/psycopg sync driver that ships
    # with the Postgres image. For SQLite tests we'd strip "+aiosqlite", but
    # we never start the scheduler from tests, so the branch is informational.
    sync_url = settings.DATABASE_URL
    for marker in ("+asyncpg", "+aiosqlite", "+psycopg_async"):
        sync_url = sync_url.replace(marker, "")

    jobstores = {"default": SQLAlchemyJobStore(url=sync_url, tablename="apscheduler_jobs")}
    _scheduler = AsyncIOScheduler(jobstores=jobstores, timezone=timezone.utc)
    _scheduler.start()
    await reconcile_jobs()
    logger.info("Scheduler started; %d job(s) registered", len(_scheduler.get_jobs()))


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
