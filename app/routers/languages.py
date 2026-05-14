"""University language definitions — CRUD per tenant."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.language import UniversityLanguage
from app.models.user import User
from app.schemas.language import LanguageIn, LanguageOut, LanguageUpdate


router = APIRouter(prefix="/languages", tags=["languages"])


def _to_out(lang: UniversityLanguage) -> LanguageOut:
    return LanguageOut.model_validate(lang)


@router.get("", response_model=list[LanguageOut])
async def list_languages(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[LanguageOut]:
    rows = (
        await db.execute(
            select(UniversityLanguage)
            .where(UniversityLanguage.user_id == current.id)
            .order_by(UniversityLanguage.language_label.asc())
        )
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=LanguageOut, status_code=status.HTTP_201_CREATED)
async def create_language(
    payload: LanguageIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LanguageOut:
    new = UniversityLanguage(
        user_id=current.id,
        iso_code=payload.iso_code,
        language_label=payload.language_label,
        university_name=payload.university_name,
    )
    db.add(new)
    await db.commit()
    await db.refresh(new)
    return _to_out(new)


@router.put("/{lang_id}", response_model=LanguageOut)
async def update_language(
    lang_id: UUID,
    payload: LanguageUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LanguageOut:
    row = await db.get(UniversityLanguage, lang_id)
    if row is None or row.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found")
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.delete("/{lang_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(
    lang_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(UniversityLanguage, lang_id)
    if row is None or row.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found")
    await db.delete(row)
    await db.commit()
