"""Run lifecycle + result selection + CSV export (affiliation-aware reads)."""
import csv
import io
from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.result import Result
from app.models.run import Run, RunStatus, RunTrigger
from app.models.search import Search
from app.models.user import User
from app.schemas.run import (
    BulkDeleteRequest,
    EmailExportRequest,
    ResultOut,
    ResultSelectionUpdate,
    ResultsPage,
    RunCreate,
    RunOut,
)
from app.services.scoping import shared_read_filter
from app.services.search_engine import execute_run


router = APIRouter(prefix="/runs", tags=["runs"])


async def _selected_results_csv(db: AsyncSession, run_ids: list[UUID]) -> tuple[bytes, int]:
    """Build the UTF-8-BOM CSV of all ``is_selected`` results across runs.

    Shared by the download (`/runs/export`) and email (`/runs/export-email`)
    paths. Returns ``(csv_bytes, row_count)``.
    """
    rows = (
        await db.execute(
            select(Result).where(Result.run_id.in_(run_ids), Result.is_selected.is_(True))
        )
    ).scalars().all()

    # Date descending, blank dates last (stable across the multi-key sorts).
    rows_sorted: Sequence[Result] = sorted(rows, key=lambda r: r.date_extracted or "", reverse=True)
    rows_sorted = sorted(rows_sorted, key=lambda r: 0 if r.date_extracted else 1)

    buf = io.StringIO()
    buf.write("﻿")  # BOM for Excel UTF-8
    writer = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    writer.writerow(["Date", "Media", "Language", "Headline", "URL"])
    for r in rows_sorted:
        writer.writerow([
            r.date_extracted,
            r.outlet_name,
            (r.detected_lang or "").upper(),
            r.title,
            r.url,
        ])
    return buf.getvalue().encode("utf-8"), len(rows_sorted)


async def _authorize_runs(db: AsyncSession, run_ids: list[UUID], current: User) -> None:
    """Raise 400/403 unless every run in ``run_ids`` is visible to ``current``."""
    if not run_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No run_ids provided")
    runs = (
        await db.execute(
            select(Run.id).where(Run.id.in_(run_ids), shared_read_filter(Run, current))
        )
    ).scalars().all()
    visible_ids = set(runs)
    for rid in run_ids:
        if rid not in visible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorised for run {rid}"
            )


async def _run_to_out(
    db: AsyncSession,
    run: Run,
    *,
    search_name: str | None = None,
    performer_email: str | None = None,
) -> RunOut:
    count = (
        await db.execute(select(func.count(Result.id)).where(Result.run_id == run.id))
    ).scalar_one()
    return RunOut(
        id=run.id,
        search_id=run.search_id,
        triggered_by=run.triggered_by,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        api_calls_used=run.api_calls_used,
        error_message=run.error_message,
        search_name=search_name,
        result_count=int(count or 0),
        user_id=run.user_id,
        university_id=run.university_id,
        performed_by_email=performer_email,
    )


async def _can_view_run(run: Run, current: User) -> bool:
    """A run is visible if the user owns it OR shares its affiliation snapshot."""
    if run.user_id == current.id:
        return True
    if current.university_id is not None and run.university_id == current.university_id:
        return True
    return False


@router.get("", response_model=list[RunOut])
async def list_runs(
    search_id: UUID | None = None,
    status_filter: RunStatus | None = Query(default=None, alias="status"),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[RunOut]:
    stmt = (
        select(Run, Search.name, User.email)
        .join(Search, Search.id == Run.search_id)
        .join(User, User.id == Run.user_id)
        .where(shared_read_filter(Run, current))
        .order_by(Run.started_at.desc())
    )
    if search_id is not None:
        stmt = stmt.where(Run.search_id == search_id)
    if status_filter is not None:
        stmt = stmt.where(Run.status == status_filter)
    rows = (await db.execute(stmt)).all()
    out: list[RunOut] = []
    for run, name, email in rows:
        out.append(
            await _run_to_out(db, run, search_name=name, performer_email=email)
        )
    return out


@router.post("", response_model=RunOut, status_code=status.HTTP_202_ACCEPTED)
async def trigger_run(
    payload: RunCreate,
    background: BackgroundTasks,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunOut:
    # Searches remain user-private even with affiliation, so the existing
    # ownership check still applies.
    search = await db.get(Search, payload.search_id)
    if search is None or search.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    if not current.google_api_key_encrypted or not current.search_engine_id_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Configure your Google API credentials in Settings before running a search.",
        )
    from app.routers.searches import validate_search_config
    if not validate_search_config(search.config or {}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search has no active terms, DOI, or university name — add something to search for.",
        )
    run = Run(
        user_id=current.id,
        search_id=search.id,
        # Snapshot affiliation at run-creation time (§8.3). The run stays with
        # this university even if the user is later reassigned.
        university_id=current.university_id,
        triggered_by=RunTrigger.manual,
        status=RunStatus.pending,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    background.add_task(execute_run, run.id, deduplicate=payload.deduplicate)
    return await _run_to_out(
        db, run, search_name=search.name, performer_email=current.email
    )


@router.get("/merged", response_model=ResultsPage)
async def get_merged_results(
    run_ids: list[UUID] = Query(..., alias="run_ids[]"),
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResultsPage:
    """Return deduplicated results from multiple runs (temporary merge, not persisted)."""
    if not run_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No run_ids provided")
    runs = (
        await db.execute(
            select(Run).where(Run.id.in_(run_ids), shared_read_filter(Run, current))
        )
    ).scalars().all()
    visible_ids = {r.id for r in runs}
    for rid in run_ids:
        if rid not in visible_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorised for run {rid}"
            )

    all_results = (
        await db.execute(
            select(Result)
            .where(Result.run_id.in_(run_ids))
            .order_by(Result.date_extracted.desc(), Result.created_at.asc())
        )
    ).scalars().all()

    seen_urls: set[str] = set()
    deduplicated: list[Result] = []
    for r in all_results:
        if r.url not in seen_urls:
            seen_urls.add(r.url)
            deduplicated.append(r)

    total = len(deduplicated)
    start = (page - 1) * page_size
    page_items = deduplicated[start: start + page_size]

    return ResultsPage(
        items=[ResultOut.model_validate(r) for r in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export")
async def export_runs(
    run_ids: list[UUID] = Query(..., alias="run_ids[]"),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export all `is_selected=true` results across the given runs as a single CSV."""
    await _authorize_runs(db, run_ids, current)
    out_bytes, _ = await _selected_results_csv(db, run_ids)

    from datetime import date

    filename = f"media_hits_{date.today().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        io.BytesIO(out_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/export-email")
async def export_runs_email(
    payload: EmailExportRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Email the CSV of selected hits across the given runs to an address.

    Same CSV as ``/runs/export``, delivered as an attachment to the supplied
    address (the UI pre-fills the requester's own login email but allows any).
    """
    await _authorize_runs(db, payload.run_ids, current)
    out_bytes, count = await _selected_results_csv(db, payload.run_ids)
    if count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No selected hits to export — tick at least one result first.",
        )

    from datetime import date

    from app.services.email import send_export_email

    filename = f"media_hits_{date.today().strftime('%Y%m%d')}.csv"
    sent = await send_export_email(str(payload.email), out_bytes, filename, count)
    if not sent:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Email could not be sent (mail server not configured or unavailable). "
            "Use Download instead.",
        )
    return {"sent": True, "email": str(payload.email), "count": count}


@router.get("/{run_id}", response_model=RunOut)
async def get_run(
    run_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunOut:
    run = await db.get(Run, run_id)
    if run is None or not await _can_view_run(run, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    search = await db.get(Search, run.search_id)
    performer = await db.get(User, run.user_id)
    return await _run_to_out(
        db,
        run,
        search_name=search.name if search else None,
        performer_email=performer.email if performer else None,
    )


@router.get("/{run_id}/results", response_model=ResultsPage)
async def get_results(
    run_id: UUID,
    lang: str | None = None,
    selected: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(200, ge=1, le=1000),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ResultsPage:
    run = await db.get(Run, run_id)
    if run is None or not await _can_view_run(run, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    stmt = select(Result).where(Result.run_id == run_id)
    if lang:
        stmt = stmt.where(Result.detected_lang == lang.lower())
    if selected is not None:
        stmt = stmt.where(Result.is_selected.is_(selected))
    total = (
        await db.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    stmt = (
        stmt.order_by(Result.detected_lang.asc(), Result.date_extracted.desc(), Result.created_at.asc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return ResultsPage(
        items=[ResultOut.model_validate(r) for r in rows],
        total=int(total or 0),
        page=page,
        page_size=page_size,
    )


@router.patch("/{run_id}/results", status_code=status.HTTP_204_NO_CONTENT)
async def update_result_selection(
    run_id: UUID,
    payload: ResultSelectionUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Any member who can see the run can toggle selections on it (shared
    # editing for the review/export workflow). Only the performer can delete.
    run = await db.get(Run, run_id)
    if run is None or not await _can_view_run(run, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if not payload.result_ids:
        return
    await db.execute(
        update(Result)
        .where(Result.id.in_(payload.result_ids), Result.run_id == run_id)
        .values(is_selected=payload.selected)
    )
    await db.commit()


@router.post("/{run_id}/cancel", response_model=RunOut)
async def cancel_run(
    run_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RunOut:
    """Stop a pending/running run. Any member who can see it may cancel it.

    Marks the run failed with a "Cancelled" message; the background executor
    notices the status change between pages and stops, keeping whatever
    partial results it already saved.
    """
    run = await db.get(Run, run_id)
    if run is None or not await _can_view_run(run, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status not in (RunStatus.pending, RunStatus.running):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is no longer in progress.",
        )
    from datetime import datetime, timezone

    run.status = RunStatus.failed
    run.error_message = f"Cancelled by {current.email}."
    run.completed_at = datetime.now(timezone.utc)
    await db.commit()
    search = await db.get(Search, run.search_id)
    performer = await db.get(User, run.user_id)
    return await _run_to_out(
        db,
        run,
        search_name=search.name if search else None,
        performer_email=performer.email if performer else None,
    )


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Any member who can see the run (its performer, or anyone sharing its
    # university affiliation) may delete it. This keeps shared run history
    # tidy — e.g. removing ghost entries left behind after a member leaves.
    run = await db.get(Run, run_id)
    if run is None or not await _can_view_run(run, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    await db.delete(run)
    await db.commit()


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_runs(
    payload: BulkDeleteRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not payload.run_ids:
        return
    # Deletable = any run visible under the affiliation scope (see delete_run).
    visible = (
        await db.execute(
            select(Run.id).where(
                Run.id.in_(payload.run_ids), shared_read_filter(Run, current)
            )
        )
    ).scalars().all()
    visible_set = set(visible)
    for rid in payload.run_ids:
        if rid not in visible_set:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=f"Not authorised for run {rid}"
            )
    runs = (
        await db.execute(select(Run).where(Run.id.in_(payload.run_ids)))
    ).scalars().all()
    for run in runs:
        await db.delete(run)
    await db.commit()
