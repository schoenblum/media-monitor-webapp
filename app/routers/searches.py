"""Search CRUD — all configuration is stored in the searches.config JSONB column."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.search import DEFAULT_SEARCH_CONFIG, Search
from app.models.user import User
from app.schemas.search import SearchConfig, SearchCreate, SearchOut, SearchUpdate


router = APIRouter(prefix="/searches", tags=["searches"])


def _search_to_out(s: Search) -> SearchOut:
    return SearchOut(
        id=s.id,
        name=s.name,
        is_default=s.is_default,
        config=s.config or dict(DEFAULT_SEARCH_CONFIG),
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


async def _clear_default(db: AsyncSession, user_id: UUID, except_id: UUID | None = None) -> None:
    stmt = (
        update(Search)
        .where(Search.user_id == user_id, Search.is_default.is_(True))
        .values(is_default=False)
    )
    if except_id is not None:
        stmt = stmt.where(Search.id != except_id)
    await db.execute(stmt)


async def _load_for_user(db: AsyncSession, user_id: UUID, search_id: UUID) -> Search:
    row = (
        await db.execute(
            select(Search).where(Search.id == search_id, Search.user_id == user_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return row


@router.get("", response_model=list[SearchOut])
async def list_searches(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SearchOut]:
    rows = (
        await db.execute(
            select(Search)
            .where(Search.user_id == current.id)
            .order_by(Search.is_default.desc(), Search.name.asc())
        )
    ).scalars().all()
    return [_search_to_out(s) for s in rows]


@router.post("", response_model=SearchOut, status_code=status.HTTP_201_CREATED)
async def create_search(
    payload: SearchCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    if payload.is_default:
        await _clear_default(db, current.id)
    new = Search(
        user_id=current.id,
        name=payload.name.strip(),
        is_default=payload.is_default,
        config=payload.config.model_dump(),
    )
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return _search_to_out(new)


@router.get("/{search_id}", response_model=SearchOut)
async def get_search(
    search_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    s = await _load_for_user(db, current.id, search_id)
    return _search_to_out(s)


@router.put("/{search_id}", response_model=SearchOut)
async def update_search(
    search_id: UUID,
    payload: SearchUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    s = await _load_for_user(db, current.id, search_id)
    if payload.name is not None:
        s.name = payload.name.strip()
    if payload.is_default is True:
        await _clear_default(db, current.id, except_id=s.id)
        s.is_default = True
    elif payload.is_default is False:
        s.is_default = False
    if payload.config is not None:
        s.config = payload.config.model_dump()
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return _search_to_out(s)


@router.delete("/{search_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_search(
    search_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    s = await _load_for_user(db, current.id, search_id)
    await db.delete(s)
    await db.commit()


def validate_search_config(config: dict) -> bool:
    """Return True if the config has at least one actionable query."""
    terms = config.get("terms", [])
    has_term = any(t.get("text", "").strip() for t in terms)
    doi_text = config.get("doi", {}).get("text", "").strip()
    uni = config.get("university_name", {})
    has_uni = uni.get("enabled") and bool(uni.get("language_ids"))
    return has_term or bool(doi_text) or has_uni
