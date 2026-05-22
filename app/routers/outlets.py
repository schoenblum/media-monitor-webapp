"""Outlet CRUD plus CSV bulk import / export endpoints (affiliation-aware)."""
import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.outlet import Outlet
from app.models.user import User
from app.schemas.outlet import (
    ImportReport,
    ImportReportRow,
    OutletCommitItem,  # noqa: F401  (re-exported via OutletCommitRequest)
    OutletCommitRequest,
    OutletCommitReport,
    OutletCreate,
    OutletDuplicateRow,
    OutletOut,
    OutletPreviewResponse,
    OutletPreviewRow,
    OutletUpdate,
    _DOMAIN_RE,
)
from app.schemas.outlet import _clean_domain  # type: ignore[attr-defined]
from app.services.scoping import (
    can_modify_shared_row,
    shared_read_filter,
    shared_write_owner,
)


router = APIRouter(prefix="/outlets", tags=["outlets"])

CSV_HEADERS = ("name", "domain", "category", "keyword_langs", "notes")


def _outlet_to_out(o: Outlet) -> OutletOut:
    return OutletOut.model_validate(o)


async def _existing_by_domain(db: AsyncSession, current: User) -> dict[str, Outlet]:
    rows = (
        await db.execute(select(Outlet).where(shared_read_filter(Outlet, current)))
    ).scalars().all()
    return {o.domain: o for o in rows}


@router.get("", response_model=list[OutletOut])
async def list_outlets(
    category: str | None = None,
    active: bool | None = None,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OutletOut]:
    stmt = select(Outlet).where(shared_read_filter(Outlet, current))
    if category:
        stmt = stmt.where(Outlet.category == category)
    if active is not None:
        stmt = stmt.where(Outlet.is_active == active)
    stmt = stmt.order_by(Outlet.name.asc())
    rows = (await db.execute(stmt)).scalars().all()
    return [_outlet_to_out(o) for o in rows]


@router.post("", response_model=OutletOut, status_code=status.HTTP_201_CREATED)
async def create_outlet(
    payload: OutletCreate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutletOut:
    existing = await _existing_by_domain(db, current)
    if payload.domain in existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An outlet with that domain already exists"
        )
    o = Outlet(
        user_id=current.id,
        university_id=shared_write_owner(current),
        name=payload.name.strip(),
        domain=payload.domain,
        category=payload.category,
        keyword_langs=payload.keyword_langs,
        is_active=payload.is_active,
    )
    db.add(o)
    await db.commit()
    await db.refresh(o)
    return _outlet_to_out(o)


@router.put("/{outlet_id}", response_model=OutletOut)
async def update_outlet(
    outlet_id: UUID,
    payload: OutletUpdate,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutletOut:
    o = await db.get(Outlet, outlet_id)
    if o is None or not can_modify_shared_row(o, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    data = payload.model_dump(exclude_unset=True)
    if "domain" in data and data["domain"] and data["domain"] != o.domain:
        existing = await _existing_by_domain(db, current)
        clash = existing.get(data["domain"])
        if clash is not None and clash.id != o.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Domain already used by another outlet"
            )
    for key, value in data.items():
        setattr(o, key, value)
    await db.commit()
    await db.refresh(o)
    return _outlet_to_out(o)


@router.post("/bulk-delete", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_outlets(
    payload: dict,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    raw_ids = payload.get("outlet_ids") or []
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
            select(Outlet).where(
                Outlet.id.in_(ids), shared_read_filter(Outlet, current)
            )
        )
    ).scalars().all()
    for o in rows:
        await db.delete(o)
    await db.commit()


@router.delete("/{outlet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outlet(
    outlet_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    o = await db.get(Outlet, outlet_id)
    if o is None or not can_modify_shared_row(o, current):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    await db.delete(o)
    await db.commit()


# ---------------------------------------------------------------------------
# CSV import / export
# ---------------------------------------------------------------------------


def _build_template_csv() -> bytes:
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM for Excel
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(list(CSV_HEADERS))
    w.writerow([
        "Example Outlet",
        "example.com",
        "Outstanding international importance",
        "en,de",
        "comma-separated language codes; notes column is ignored on import",
    ])
    return buf.getvalue().encode("utf-8")


@router.get("/import/template")
async def download_import_template(_: User = Depends(get_current_user)) -> StreamingResponse:
    data = _build_template_csv()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="outlet_import_template.csv"'},
    )


@router.get("/export")
async def export_outlets(
    current: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    rows = (
        await db.execute(
            select(Outlet)
            .where(shared_read_filter(Outlet, current))
            .order_by(Outlet.name.asc())
        )
    ).scalars().all()
    buf = io.StringIO()
    buf.write("﻿")  # UTF-8 BOM
    w = csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    w.writerow(list(CSV_HEADERS))
    for o in rows:
        w.writerow([
            o.name,
            o.domain,
            o.category or "",
            ",".join(o.keyword_langs or []),
            "active" if o.is_active else "inactive",
        ])
    out_bytes = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(out_bytes),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="outlets_export.csv"'},
    )


@router.post("/import", response_model=ImportReport)
async def import_outlets(
    file: UploadFile = File(...),
    mode: str = Query("add", pattern="^(replace|add)$"),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ImportReport:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a .csv file"
        )
    body_bytes = await file.read()
    body_str = body_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(body_str))

    try:
        headers_row = next(reader)
    except StopIteration:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty CSV file")

    header_map = {h.strip().lower(): i for i, h in enumerate(headers_row)}
    for required in ("name", "domain"):
        if required not in header_map:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Missing required column: {required}",
            )

    uni_id = shared_write_owner(current)

    if mode == "replace":
        existing_rows = (
            await db.execute(select(Outlet).where(shared_read_filter(Outlet, current)))
        ).scalars().all()
        for o in existing_rows:
            await db.delete(o)
        await db.flush()
        existing_domains: set[str] = set()
    else:
        existing_domains = set((await _existing_by_domain(db, current)).keys())

    imported = 0
    skipped: list[ImportReportRow] = []

    for i, row in enumerate(reader, start=2):
        try:
            name = row[header_map["name"]].strip() if len(row) > header_map["name"] else ""
            domain_raw = row[header_map["domain"]].strip() if len(row) > header_map["domain"] else ""
        except IndexError:
            skipped.append(ImportReportRow(row=i, reason="Row too short"))
            continue

        if not name or not domain_raw:
            skipped.append(ImportReportRow(row=i, reason="Missing name or domain"))
            continue

        domain = _clean_domain(domain_raw)
        if not domain:
            skipped.append(ImportReportRow(row=i, reason="Invalid domain"))
            continue
        if domain in existing_domains:
            skipped.append(ImportReportRow(row=i, reason=f"Duplicate domain: {domain}"))
            continue

        category = None
        if "category" in header_map and len(row) > header_map["category"]:
            category = row[header_map["category"]].strip() or None

        langs: list[str] = []
        if "keyword_langs" in header_map and len(row) > header_map["keyword_langs"]:
            raw_langs = row[header_map["keyword_langs"]]
            for token in raw_langs.replace(";", ",").split(","):
                t = token.strip().lower()
                if t:
                    langs.append(t)

        db.add(
            Outlet(
                user_id=current.id,
                university_id=uni_id,
                name=name,
                domain=domain,
                category=category,
                keyword_langs=langs,
                is_active=True,
            )
        )
        existing_domains.add(domain)
        imported += 1

    await db.commit()
    return ImportReport(imported=imported, skipped=skipped)


# ---------------------------------------------------------------------------
# Preview / commit (duplicate-resolution flow)
# ---------------------------------------------------------------------------


def _parse_outlet_csv(body_bytes: bytes) -> tuple[list[dict], list[str]]:
    body_str = body_bytes.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(body_str))
    parse_errors: list[str] = []

    try:
        headers_row = next(reader)
    except StopIteration:
        return [], ["Empty CSV file"]
    header_map = {h.strip().lower(): i for i, h in enumerate(headers_row)}
    for required in ("name", "domain"):
        if required not in header_map:
            return [], [f"Missing required column: {required}"]

    rows: list[dict] = []
    for i, row in enumerate(reader, start=2):
        try:
            name = row[header_map["name"]].strip() if len(row) > header_map["name"] else ""
            domain_raw = row[header_map["domain"]].strip() if len(row) > header_map["domain"] else ""
        except IndexError:
            parse_errors.append(f"Row {i}: too short")
            continue
        if not name and not domain_raw:
            continue
        if not name or not domain_raw:
            parse_errors.append(f"Row {i}: missing name or domain")
            continue
        domain = _clean_domain(domain_raw)
        if not _DOMAIN_RE.match(domain):
            parse_errors.append(f"Row {i}: invalid domain '{domain_raw}'")
            continue

        category = None
        if "category" in header_map and len(row) > header_map["category"]:
            category = row[header_map["category"]].strip() or None

        langs: list[str] = []
        if "keyword_langs" in header_map and len(row) > header_map["keyword_langs"]:
            raw_langs = row[header_map["keyword_langs"]]
            for token in raw_langs.replace(";", ",").split(","):
                t = token.strip().lower()
                if t:
                    langs.append(t)

        rows.append({
            "row_num": i,
            "name": name,
            "domain": domain,
            "category": category,
            "keyword_langs": langs,
        })
    return rows, parse_errors


@router.post("/import/preview", response_model=OutletPreviewResponse)
async def preview_outlet_import(
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutletPreviewResponse:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Please upload a .csv file"
        )
    body = await file.read()
    rows, parse_errors = _parse_outlet_csv(body)

    existing_by_domain = await _existing_by_domain(db, current)

    new_rows: list[OutletPreviewRow] = []
    duplicate_rows: list[OutletDuplicateRow] = []
    seen_in_file: set[str] = set()

    for r in rows:
        domain = r["domain"]
        if domain in seen_in_file:
            parse_errors.append(f"Row {r['row_num']}: duplicate domain '{domain}' within file (kept first)")
            continue
        seen_in_file.add(domain)
        if domain in existing_by_domain:
            existing = existing_by_domain[domain]
            duplicate_rows.append(
                OutletDuplicateRow(
                    row_num=r["row_num"],
                    domain=domain,
                    new_name=r["name"],
                    new_category=r["category"],
                    new_keyword_langs=r["keyword_langs"],
                    existing_id=existing.id,
                    existing_name=existing.name,
                    existing_category=existing.category,
                    existing_keyword_langs=list(existing.keyword_langs or []),
                )
            )
        else:
            new_rows.append(
                OutletPreviewRow(
                    row_num=r["row_num"],
                    name=r["name"],
                    domain=domain,
                    category=r["category"],
                    keyword_langs=r["keyword_langs"],
                )
            )

    return OutletPreviewResponse(
        new_rows=new_rows,
        duplicate_rows=duplicate_rows,
        parse_errors=parse_errors,
    )


@router.post("/import/commit", response_model=OutletCommitReport)
async def commit_outlet_import(
    payload: OutletCommitRequest,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OutletCommitReport:
    uni_id = shared_write_owner(current)

    if payload.mode == "replace":
        existing = (
            await db.execute(select(Outlet).where(shared_read_filter(Outlet, current)))
        ).scalars().all()
        deleted = len(existing)
        for o in existing:
            await db.delete(o)
        await db.flush()

        added = 0
        seen: set[str] = set()
        for item in payload.items:
            if item.domain in seen:
                continue
            seen.add(item.domain)
            db.add(
                Outlet(
                    user_id=current.id,
                    university_id=uni_id,
                    name=item.name,
                    domain=item.domain,
                    category=item.category,
                    keyword_langs=item.keyword_langs,
                    is_active=True,
                )
            )
            added += 1
        await db.commit()
        return OutletCommitReport(added=added, replaced=0, deleted=deleted)

    by_domain = await _existing_by_domain(db, current)
    added = 0
    replaced = 0
    for item in payload.items:
        if item.replace_existing_id is not None:
            row = await db.get(Outlet, item.replace_existing_id)
            if row is None or not can_modify_shared_row(row, current):
                continue
            row.name = item.name
            row.domain = item.domain
            row.category = item.category
            row.keyword_langs = item.keyword_langs
            replaced += 1
            continue
        if item.domain in by_domain:
            continue
        new_o = Outlet(
            user_id=current.id,
            university_id=uni_id,
            name=item.name,
            domain=item.domain,
            category=item.category,
            keyword_langs=item.keyword_langs,
            is_active=True,
        )
        db.add(new_o)
        by_domain[item.domain] = new_o
        added += 1
    await db.commit()
    return OutletCommitReport(added=added, replaced=replaced, deleted=0)
