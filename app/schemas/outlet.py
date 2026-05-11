"""Pydantic schemas for outlets and the import / export endpoints."""
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.default_outlets import SUPPORTED_LANGUAGES


_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+(/[a-z0-9._~%/-]*)?$")


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
            if c not in SUPPORTED_LANGUAGES:
                raise ValueError(f"Unsupported language code: {code}")
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
            if c not in SUPPORTED_LANGUAGES:
                raise ValueError(f"Unsupported language code: {code}")
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
