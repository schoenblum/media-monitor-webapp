"""Webhook endpoint — external systems can trigger a run with an API key."""
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run, RunStatus, RunTrigger
from app.models.search import Search
from app.models.user import User
from app.services.search_engine import execute_run
from app.services.security import verify_token


router = APIRouter(prefix="/webhook", tags=["webhook"])


class WebhookRunRequest(BaseModel):
    search_id: UUID


class WebhookRunResponse(BaseModel):
    run_id: UUID
    status: RunStatus


@router.post("/run", response_model=WebhookRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_via_webhook(
    payload: WebhookRunRequest,
    background: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> WebhookRunResponse:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-API-Key")

    candidates = (
        await db.execute(
            select(User).where(User.webhook_api_key_hash.is_not(None), User.is_active.is_(True))
        )
    ).scalars().all()

    user: User | None = None
    for candidate in candidates:
        if candidate.webhook_api_key_hash and verify_token(x_api_key, candidate.webhook_api_key_hash):
            user = candidate
            break
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    search = await db.get(Search, payload.search_id)
    if search is None or search.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    if not user.google_api_key_encrypted or not user.search_engine_id_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google credentials not configured for this account.",
        )

    run = Run(
        user_id=user.id,
        search_id=search.id,
        # Snapshot the performing user's affiliation, same rule as the manual
        # trigger (revision_brief_v2.2.md §8.3).
        university_id=user.university_id,
        triggered_by=RunTrigger.webhook,
        status=RunStatus.pending,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    # Webhook trigger always dedupes — external callers can't reasonably reach
    # in to override per-run, and a recurring webhook would otherwise re-surface
    # the same hits every fire (item 4b).
    background.add_task(execute_run, run.id, deduplicate=True)
    return WebhookRunResponse(run_id=run.id, status=run.status)
