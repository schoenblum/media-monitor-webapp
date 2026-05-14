"""Pydantic schemas for university language definitions + CSV import flow."""
import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ISO_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def _normalize_iso(v: str) -> str:
    v = v.strip().lower()
    if not _ISO_RE.match(v):
        raise ValueError(f"Invalid ISO 639-1/BCP-47 code: {v}")
    return v


class LanguageIn(BaseModel):
    iso_code: str = Field(min_length=2, max_length=10)
    university_name: str = Field(min_length=1, max_length=255)

    @field_validator("iso_code")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        return _normalize_iso(v)

    @field_validator("university_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LanguageUpdate(BaseModel):
    iso_code: str | None = Field(default=None, min_length=2, max_length=10)
    university_name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("iso_code")
    @classmethod
    def _validate_iso(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return _normalize_iso(v)


class LanguageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    iso_code: str
    university_name: str
    created_at: datetime


# ---------------------------------------------------------------------------
# CSV import — preview / commit
# ---------------------------------------------------------------------------


class LanguagePreviewRow(BaseModel):
    """One row from a CSV import — ISO valid and not already taken."""
    row_num: int
    iso_code: str
    university_name: str


class LanguageInvalidIsoRow(BaseModel):
    """Row whose ISO code isn't in the supported list — user must pick one."""
    row_num: int
    raw_iso: str
    university_name: str


class LanguageDuplicateRow(BaseModel):
    """Row whose ISO matches an existing entry — user picks existing vs new."""
    row_num: int
    iso_code: str
    new_university_name: str
    existing_id: UUID
    existing_university_name: str


class LanguagePreviewResponse(BaseModel):
    new_rows: list[LanguagePreviewRow] = []
    invalid_iso_rows: list[LanguageInvalidIsoRow] = []
    duplicate_rows: list[LanguageDuplicateRow] = []
    parse_errors: list[str] = []


class LanguageCommitItem(BaseModel):
    iso_code: str = Field(min_length=2, max_length=10)
    university_name: str = Field(min_length=1, max_length=255)
    replace_existing_id: UUID | None = None

    @field_validator("iso_code")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        return _normalize_iso(v)

    @field_validator("university_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LanguageCommitRequest(BaseModel):
    mode: Literal["add", "replace"] = "add"
    items: list[LanguageCommitItem] = []


class LanguageCommitReport(BaseModel):
    added: int
    replaced: int
    deleted: int
