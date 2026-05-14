"""Outlet CRUD plus CSV bulk import / export endpoints."""
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
    OutletCreate,
    OutletOut,
    OutletUpdate,
)
from app.schemas.outlet import _clean_domain  # type: ignore[attr-defined]


router = APIRouter(prefix="/outlets", tags=["outlets"])

CSV_HEADERS = ("name", "domain", "category", "keyword_langs", "notes")


def _outlet_to_out(o: Outlet) -> OutletOut:
    return OutletOut.model_validate(o)


@router.get("", response_model=list[OutletOut])
async def list_outlets(
    category: str | None = None,
    active: bool | None = None,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OutletOut]:
    stmt = select(Outlet).where(Outlet.user_id == current.id)
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
    existing = (
        await db.execute(
            select(Outlet).where(Outlet.user_id == current.id, Outlet.domain == payload.domain)
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="An outlet with that domain already exists"
        )
    o = Outlet(
        user_id=current.id,
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
    if o is None or o.user_id != current.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outlet not found")
    data = payload.model_dump(exclude_unset=True)
    if "domain" in data and data["domain"]:
        if data["domain"] != o.domain:
            clash = (
                await db.execute(
                    select(Outlet).where(
                        Outlet.user_id == current.id, Outlet.domain == data["domain"]
                    )
                )
            ).scalar_one_or_none()
            if clash is not None and clash.id != o.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Domain already used by another outlet"
                )
    for key, value in data.items():
        setattr(o, key, value)
    await db.commit()
    await db.refresh(o)
    return _outlet_to_out(o)


@router.delete("/{outlet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_outlet(
    outlet_id: UUID,
    current: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    o = await db.get(Outlet, outlet_id)
    if o is None or o.user_id != current.id:
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
            select(Outlet).where(Outlet.user_id == current.id).order_by(Outlet.name.asc())
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
    # Strip UTF-8 BOM if present
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

    if mode == "replace":
        existing_rows = (
            await db.execute(select(Outlet).where(Outlet.user_id == current.id))
        ).scalars().all()
        for o in existing_rows:
            await db.delete(o)
        await db.flush()
        existing_domains: set[str] = set()
    else:
        existing_domains = {
            d for (d,) in (
                await db.execute(select(Outlet.domain).where(Outlet.user_id == current.id))
            ).all()
        }

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
