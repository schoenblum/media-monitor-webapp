"""University language definitions — affiliation-aware CRUD + CSV import / export.

When the current user is affiliated, languages are *shared* across the
university (any member can view or edit, last-write-wins). When unaffiliated,
behaviour is exactly as in v2.1: rows are private to ``user_id`` and carry
``university_id == NULL``. See ``app/services/scoping.py``.
"""
import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.language import UniversityLanguage
from app.models.user import User
from app.schemas.language import (
    LanguageCommitItem,
    LanguageCommitReport,
    LanguageCommitRequest,
    LanguageDuplicateRow,
    LanguageIn,
    LanguageInvalidIsoRow,
    LanguageOut,
    LanguagePreviewResponse,
    LanguagePreviewRow,
    LanguageUpdate,
)
from app.services.languages import is_supported
from app.services.scoping import (
    can_modify_shared_row,
    shared_read_filter,
    shared_write_owner,
)


router = APIRouter(prefix="/languages", tags=["languages"])

CSV_HEADERS = ("iso_code", "university_name")


def _to_out(lang: UniversityLanguage) -> LanguageOut:
    return LanguageOut.model_validate(lang)


async def _existing_by_iso(
    db: AsyncSession, current: User
) -> dict[str, UniversityLanguage]:
    """Return the user's visible language rows keyed by lowercased iso_code."""
    rows = (
        await db.execute(
            select(UniversityLanguage).where(
                shared_read_filter(UniversityLanguage, current)
            )
        )
    ).scalars().all()
    return {r.iso_code: r for r in rows}


@router.get("", response_model=list[LanguageOut])
async def list_languages(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[LanguageOut]:
    rows = (
        await db.execute(
            select(UniversityLanguage)
            .where(shared_read_filter(UniversityLanguage, current))
            .order_by(UniversityLanguage.iso_code.asc())
        )
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=LanguageOut, status_code=status.HTTP_201_CREATED)
async def create_language(
    payload: LanguageIn,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LanguageOut:
    existing = await _existing_by_iso(db, current)
    if payload.iso_code in existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"You already have an entry for ISO code '{payload.iso_code}'.",
        )
    new = UniversityLanguage(
        user_id=current.id,
        university_id=shared_write_owner(current),
        iso_code=payload.iso_code,
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
    if row is None or not can_modify_shared_row(row, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found")
    data = payload.model_dump(exclude_unset=True)
    if "iso_code" in data and data["iso_code"] != row.iso_code:
        existing = await _existing_by_iso(db, current)
        clash = existing.get(data["iso_code"])
        if clash is not None and clash.id != row.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"You already have an entry for ISO code '{data['iso_code']}'.",
            )
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_languages(
    payload: dict,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    raw_ids = payload.get("language_ids") or []
    if not raw_ids:
        return
    ids: list[UUID] = []
    for x in raw_ids:
        try:
            ids.append(UUID(str(x)))
        except (TypeError, ValueError):
            continue
    if not ids:
        return
    rows = (
        await db.execute(
            select(UniversityLanguage).where(
                UniversityLanguage.id.in_(ids),
                shared_read_filter(UniversityLanguage, current),
            )
        )
    ).scalars().all()
    for r in rows:
        await db.delete(r)
    await db.commit()


@router.delete("/{lang_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_language(
    lang_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    row = await db.get(UniversityLanguage, lang_id)
    if row is None or not can_modify_shared_row(row, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Language not found")
    await db.delete(row)
    await db.commit()


# ---------------------------------------------------------------------------
# CSV import / export
# ---------------------------------------------------------------------------


def _build_template_csv() -> bytes:
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM for Excel
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(list(CSV_HEADERS))
    w.writerow(["EN", "Kobe University"])
    w.writerow(["JA", "神戸大学"])
    return buf.getvalue().encode("utf-8")


@router.get("/import/template")
async def download_import_template(_: User = Depends(get_current_user)) -> StreamingResponse:
    data = _build_template_csv()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="language_import_template.csv"'},
    )


@router.get("/export")
async def export_languages(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    rows = (
        await db.execute(
            select(UniversityLanguage)
            .where(shared_read_filter(UniversityLanguage, current))
            .order_by(UniversityLanguage.iso_code.asc())
        )
    ).scalars().all()
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(list(CSV_HEADERS))
    for r in rows:
        w.writerow([r.iso_code.upper(), r.university_name])
    out = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(out),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="languages_export.csv"'},
    )


def _parse_csv(body_bytes: bytes) -> tuple[list[tuple[int, str, str]], list[str]]:
    """Return (rows, parse_errors). Each row is (row_num, raw_iso, university_name)."""
    body_str = body_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(body_str))
    parse_errors: list[str] = []

    try:
        headers_row = next(reader)
    except StopIteration:
        return [], ["Empty CSV file"]

    header_map = {h.strip().lower(): i for i, h in enumerate(headers_row)}
    for required in CSV_HEADERS:
        if required not in header_map:
            return [], [f"Missing required column: {required}"]

    out: list[tuple[int, str, str]] = []
    for i, row in enumerate(reader, start=2):
        try:
            iso = row[header_map["iso_code"]].strip() if len(row) > header_map["iso_code"] else ""
            name = row[header_map["university_name"]].strip() if len(row) > header_map["university_name"] else ""
        except IndexError:
            parse_errors.append(f"Row {i}: too short")
            continue
        if not iso and not name:
            continue  # blank line
        if not name:
            parse_errors.append(f"Row {i}: missing university_name")
            continue
        out.append((i, iso, name))
    return out, parse_errors


@router.post("/import/preview", response_model=LanguagePreviewResponse)
async def preview_language_import(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LanguagePreviewResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a .csv file"
        )
    body = await file.read()
    rows, parse_errors = _parse_csv(body)

    existing_by_iso = await _existing_by_iso(db, current)

    new_rows: list[LanguagePreviewRow] = []
    invalid_iso_rows: list[LanguageInvalidIsoRow] = []
    duplicate_rows: list[LanguageDuplicateRow] = []
    seen_in_file: set[str] = set()

    for row_num, raw_iso, name in rows:
        normalized = raw_iso.lower()
        if not is_supported(normalized):
            invalid_iso_rows.append(
                LanguageInvalidIsoRow(row_num=row_num, raw_iso=raw_iso, university_name=name)
            )
            continue
        if normalized in seen_in_file:
            parse_errors.append(f"Row {row_num}: duplicate ISO '{raw_iso}' within file (kept first occurrence)")
            continue
        seen_in_file.add(normalized)
        if normalized in existing_by_iso:
            existing = existing_by_iso[normalized]
            duplicate_rows.append(
                LanguageDuplicateRow(
                    row_num=row_num,
                    iso_code=normalized,
                    new_university_name=name,
                    existing_id=existing.id,
                    existing_university_name=existing.university_name,
                )
            )
        else:
            new_rows.append(
                LanguagePreviewRow(row_num=row_num, iso_code=normalized, university_name=name)
            )

    return LanguagePreviewResponse(
        new_rows=new_rows,
        invalid_iso_rows=invalid_iso_rows,
        duplicate_rows=duplicate_rows,
        parse_errors=parse_errors,
    )


@router.post("/import/commit", response_model=LanguageCommitReport)
async def commit_language_import(
    payload: LanguageCommitRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LanguageCommitReport:
    uni_id = shared_write_owner(current)

    if payload.mode == "replace":
        existing = (
            await db.execute(
                select(UniversityLanguage).where(
                    shared_read_filter(UniversityLanguage, current)
                )
            )
        ).scalars().all()
        deleted = len(existing)
        for row in existing:
            await db.delete(row)
        await db.flush()

        added = 0
        seen_iso: set[str] = set()
        for item in payload.items:
            if item.iso_code in seen_iso:
                continue
            seen_iso.add(item.iso_code)
            db.add(
                UniversityLanguage(
                    user_id=current.id,
                    university_id=uni_id,
                    iso_code=item.iso_code,
                    university_name=item.university_name,
                )
            )
            added += 1
        await db.commit()
        return LanguageCommitReport(added=added, replaced=0, deleted=deleted)

    # ADD mode — items with replace_existing_id update that row; others insert new
    by_iso = await _existing_by_iso(db, current)
    added = 0
    replaced = 0
    for item in payload.items:
        if item.replace_existing_id is not None:
            row = await db.get(UniversityLanguage, item.replace_existing_id)
            if row is None or not can_modify_shared_row(row, current):
                continue
            row.iso_code = item.iso_code
            row.university_name = item.university_name
            replaced += 1
            continue
        if item.iso_code in by_iso:
            continue
        new_row = UniversityLanguage(
            user_id=current.id,
            university_id=uni_id,
            iso_code=item.iso_code,
            university_name=item.university_name,
        )
        db.add(new_row)
        by_iso[item.iso_code] = new_row
        added += 1
    await db.commit()
    return LanguageCommitReport(added=added, replaced=replaced, deleted=0)
