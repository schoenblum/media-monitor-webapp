"""Pydantic schemas for outlets and the import / export endpoints."""
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+(/[a-z0-9._~%/-]*)?$"
)
_LANG_RE = re.compile(r"^[a-z]{2,3}(-[a-zA-Z0-9]{2,8})*$")


def _clean_domain(raw: str) -> str:
    d = raw.strip().lower()
    for prefix in ("https://", "http://", "site:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d.rstrip("/")


class OutletBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=255)
    keyword_langs: list[str] = Field(default_factory=list)
    is_active: bool = True

    @field_validator("domain")
    @classmethod
    def _v_domain(cls, v: str) -> str:
        cleaned = _clean_domain(v)
        if not _DOMAIN_RE.match(cleaned):
            raise ValueError(f"Invalid domain: {v}")
        return cleaned

    @field_validator("keyword_langs")
    @classmethod
    def _v_langs(cls, v: list[str]) -> list[str]:
        out = []
        for code in v:
            c = code.strip().lower()
            if c and not _LANG_RE.match(c):
                raise ValueError(f"Invalid language code: {code}")
            if c:
                out.append(c)
        return out


class OutletCreate(OutletBase):
    pass


class OutletUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=255)
    keyword_langs: list[str] | None = None
    is_active: bool | None = None

    _v_domain = field_validator("domain")(lambda cls, v: _clean_domain(v) if v else v)  # type: ignore[assignment]

    @field_validator("keyword_langs")
    @classmethod
    def _v_langs(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out = []
        for code in v:
            c = code.strip().lower()
            if c and not _LANG_RE.match(c):
                raise ValueError(f"Invalid language code: {code}")
            if c:
                out.append(c)
        return out


class OutletOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    domain: str
    category: str | None
    keyword_langs: list[str]
    is_active: bool
    created_at: datetime


class ImportReportRow(BaseModel):
    row: int
    reason: str


class ImportReport(BaseModel):
    imported: int
    skipped: list[ImportReportRow] = []


# ---------------------------------------------------------------------------
# CSV import — preview / commit (with duplicate resolution)
# ---------------------------------------------------------------------------


class OutletPreviewRow(BaseModel):
    row_num: int
    name: str
    domain: str
    category: str | None = None
    keyword_langs: list[str] = []


class OutletDuplicateRow(BaseModel):
    row_num: int
    domain: str
    new_name: str
    new_category: str | None
    new_keyword_langs: list[str]
    existing_id: UUID
    existing_name: str
    existing_category: str | None
    existing_keyword_langs: list[str]


class OutletPreviewResponse(BaseModel):
    new_rows: list[OutletPreviewRow] = []
    duplicate_rows: list[OutletDuplicateRow] = []
    parse_errors: list[str] = []


class OutletCommitItem(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default=None, max_length=255)
    keyword_langs: list[str] = []
    replace_existing_id: UUID | None = None

    @field_validator("domain")
    @classmethod
    def _v_domain(cls, v: str) -> str:
        cleaned = _clean_domain(v)
        if not _DOMAIN_RE.match(cleaned):
            raise ValueError(f"Invalid domain: {v}")
        return cleaned

    @field_validator("keyword_langs")
    @classmethod
    def _v_langs(cls, v: list[str]) -> list[str]:
        out = []
        for code in v:
            c = code.strip().lower()
            if c and not _LANG_RE.match(c):
                raise ValueError(f"Invalid language code: {code}")
            if c:
                out.append(c)
        return out


class OutletCommitRequest(BaseModel):
    mode: Literal["add", "replace"] = "add"
    items: list[OutletCommitItem] = []


class OutletCommitReport(BaseModel):
    added: int
    replaced: int
    deleted: int
