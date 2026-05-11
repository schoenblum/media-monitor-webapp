"""Search definitions and per-search outlets / terms management."""
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.deps import get_current_user
from app.models.outlet import Outlet, SearchOutletLink
from app.models.search import Search, SearchTerm
from app.models.user import User
from app.schemas.outlet import OutletOut
from app.schemas.search import (
    LinkOutletsRequest,
    SearchCreate,
    SearchOut,
    SearchTermOut,
    SearchUpdate,
    TermsReplaceRequest,
)


router = APIRouter(prefix="/searches", tags=["searches"])


def _search_to_out(s: Search, outlet_ids: list[UUID] | None = None) -> SearchOut:
    return SearchOut(
        id=s.id,
        name=s.name,
        is_default=s.is_default,
        created_at=s.created_at,
        updated_at=s.updated_at,
        terms=[SearchTermOut.model_validate(t) for t in (s.terms or [])],
        outlet_ids=outlet_ids if outlet_ids is not None else [link.outlet_id for link in (s.outlet_links or [])],
    )


async def _clear_default(db: AsyncSession, user_id: UUID, except_id: UUID | None = None) -> None:
    stmt = update(Search).where(Search.user_id == user_id, Search.is_default.is_(True)).values(is_default=False)
    if except_id is not None:
        stmt = stmt.where(Search.id != except_id)
    await db.execute(stmt)


async def _load_for_user(db: AsyncSession, user_id: UUID, search_id: UUID) -> Search:
    stmt = (
        select(Search)
        .where(Search.id == search_id, Search.user_id == user_id)
        .options(selectinload(Search.terms), selectinload(Search.outlet_links))
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    return row


@router.get("", response_model=list[SearchOut])
async def list_searches(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SearchOut]:
    stmt = (
        select(Search)
        .where(Search.user_id == current.id)
        .options(selectinload(Search.terms), selectinload(Search.outlet_links))
        .order_by(Search.is_default.desc(), Search.name.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [_search_to_out(s) for s in rows]


@router.post("", response_model=SearchOut, status_code=status.HTTP_201_CREATED)
async def create_search(
    payload: SearchCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchOut:
    if payload.is_default:
        await _clear_default(db, current.id)
    new = Search(user_id=current.id, name=payload.name.strip(), is_default=payload.is_default)
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return _search_to_out(new, outlet_ids=[])


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


@router.put("/{search_id}/terms", response_model=list[SearchTermOut])
async def replace_terms(
    search_id: UUID,
    payload: TermsReplaceRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SearchTermOut]:
    s = await _load_for_user(db, current.id, search_id)
    # Drop existing, then replace.
    for old in list(s.terms):
        await db.delete(old)
    await db.flush()
    seen_langs: set[str] = set()
    new_rows: list[SearchTerm] = []
    for t in payload.terms:
        if t.language_code in seen_langs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate language code in terms: {t.language_code}",
            )
        seen_langs.add(t.language_code)
        new_rows.append(
            SearchTerm(
                search_id=s.id,
                language_code=t.language_code,
                term=t.term.strip(),
                pages=t.pages,
                is_enabled=t.is_enabled,
            )
        )
    db.add_all(new_rows)
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(s)
    return [SearchTermOut.model_validate(t) for t in s.terms]


@router.get("/{search_id}/outlets", response_model=list[OutletOut])
async def list_search_outlets(
    search_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OutletOut]:
    s = await _load_for_user(db, current.id, search_id)
    outlet_ids = [link.outlet_id for link in s.outlet_links]
    if not outlet_ids:
        return []
    rows = (
        await db.execute(
            select(Outlet).where(Outlet.id.in_(outlet_ids), Outlet.user_id == current.id)
        )
    ).scalars().all()
    return [OutletOut.model_validate(o) for o in rows]


@router.post("/{search_id}/outlets", status_code=status.HTTP_204_NO_CONTENT)
async def link_outlets(
    search_id: UUID,
    payload: LinkOutletsRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    s = await _load_for_user(db, current.id, search_id)
    if payload.outlet_ids:
        owned = (
            await db.execute(
                select(Outlet.id).where(
                    Outlet.id.in_(payload.outlet_ids), Outlet.user_id == current.id
                )
            )
        ).scalars().all()
        owned_set = set(owned)
        for oid in payload.outlet_ids:
            if oid not in owned_set:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Outlet {oid} not owned by user",
                )
    # Replace all links with the given set.
    for link in list(s.outlet_links):
        await db.delete(link)
    await db.flush()
    for oid in payload.outlet_ids:
        db.add(SearchOutletLink(search_id=s.id, outlet_id=oid))
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()


@router.delete("/{search_id}/outlets/{outlet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_outlet(
    search_id: UUID,
    outlet_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    s = await _load_for_user(db, current.id, search_id)
    link = next((l for l in s.outlet_links if l.outlet_id == outlet_id), None)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    await db.delete(link)
    s.updated_at = datetime.now(timezone.utc)
    await db.commit()
