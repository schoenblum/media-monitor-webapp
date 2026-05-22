"""Admin endpoints for university affiliation (Item 8 / §8.4).

Universities are an admin-only construct. Regular users see their own
affiliation via ``GET /users/me`` but cannot enumerate other universities or
change assignments.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import require_admin
from app.models.result import Result
from app.models.run import Run
from app.models.university import University
from app.models.user import User
from app.schemas.university import (
    DuplicateRunsReport,
    DuplicateRunsRequest,
    UniversityCreate,
    UniversityOut,
    UniversityUpdate,
)


router = APIRouter(prefix="/universities", tags=["universities"])


async def _to_out(db: AsyncSession, uni: University) -> UniversityOut:
    member_count = (
        await db.execute(
            select(func.count(User.id)).where(User.university_id == uni.id)
        )
    ).scalar_one()
    return UniversityOut(
        id=uni.id,
        name=uni.name,
        created_at=uni.created_at,
        updated_at=uni.updated_at,
        member_count=int(member_count or 0),
    )


@router.get("", response_model=list[UniversityOut])
async def list_universities(
    _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)
) -> list[UniversityOut]:
    rows = (
        await db.execute(select(University).order_by(University.name.asc()))
    ).scalars().all()
    return [await _to_out(db, u) for u in rows]


@router.post("", response_model=UniversityOut, status_code=status.HTTP_201_CREATED)
async def create_university(
    payload: UniversityCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UniversityOut:
    name = payload.name.strip()
    clash = (
        await db.execute(select(University).where(University.name == name))
    ).scalar_one_or_none()
    if clash is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A university named '{name}' already exists.",
        )
    uni = University(name=name)
    db.add(uni)
    await db.commit()
    await db.refresh(uni)
    return await _to_out(db, uni)


@router.put("/{university_id}", response_model=UniversityOut)
async def rename_university(
    university_id: UUID,
    payload: UniversityUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UniversityOut:
    uni = await db.get(University, university_id)
    if uni is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found")
    new_name = payload.name.strip()
    if new_name != uni.name:
        clash = (
            await db.execute(
                select(University).where(University.name == new_name)
            )
        ).scalar_one_or_none()
        if clash is not None and clash.id != uni.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A university named '{new_name}' already exists.",
            )
        uni.name = new_name
        await db.commit()
        await db.refresh(uni)
    return await _to_out(db, uni)


@router.delete("/{university_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_university(
    university_id: UUID,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    uni = await db.get(University, university_id)
    if uni is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="University not found")
    # Deletion sets university_id back to NULL on users/runs/languages/outlets
    # via the SET NULL FK action. That effectively unaffiliates every member
    # *and* orphans the shared rows back to their original creators. This is a
    # destructive admin action — the frontend will gate it behind a confirm.
    await db.delete(uni)
    await db.commit()


# ---------------------------------------------------------------------------
# Optional: duplicate a user's personal run history into a target university.
# Per §8.3, this is offered after assigning an unaffiliated user with existing
# data — the originals stay private to the user (snapshot rule), and copies
# land in the new university's shared pool with university_id set.
# ---------------------------------------------------------------------------


@router.post(
    "/duplicate-runs",
    response_model=DuplicateRunsReport,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_user_runs_into_university(
    payload: DuplicateRunsRequest,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> DuplicateRunsReport:
    source = await db.get(User, payload.user_id)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source user not found")
    target = await db.get(University, payload.target_university_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target university not found")

    # Personal runs are those not already snapshotted to the target university.
    src_runs = (
        await db.execute(
            select(Run).where(
                Run.user_id == source.id,
                (Run.university_id != target.id) | (Run.university_id.is_(None)),
            )
        )
    ).scalars().all()

    runs_copied = 0
    results_copied = 0
    for run in src_runs:
        new_run = Run(
            user_id=source.id,
            search_id=run.search_id,
            university_id=target.id,
            triggered_by=run.triggered_by,
            status=run.status,
            started_at=run.started_at,
            completed_at=run.completed_at,
            api_calls_used=run.api_calls_used,
            error_message=run.error_message,
        )
        db.add(new_run)
        await db.flush()

        src_results = (
            await db.execute(select(Result).where(Result.run_id == run.id))
        ).scalars().all()
        for r in src_results:
            db.add(
                Result(
                    run_id=new_run.id,
                    outlet_name=r.outlet_name,
                    title=r.title,
                    url=r.url,
                    display_source=r.display_source,
                    snippet=r.snippet,
                    date_extracted=r.date_extracted,
                    keyword_used=r.keyword_used,
                    search_lang=r.search_lang,
                    detected_lang=r.detected_lang,
                    detected_lang_name=r.detected_lang_name,
                    is_selected=r.is_selected,
                )
            )
            results_copied += 1
        runs_copied += 1

    await db.commit()
    return DuplicateRunsReport(runs_copied=runs_copied, results_copied=results_copied)
