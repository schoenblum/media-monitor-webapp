"""Pydantic schemas for university language definitions."""
import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ISO_RE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


class LanguageIn(BaseModel):
    iso_code: str = Field(min_length=2, max_length=10)
    language_label: str = Field(min_length=1, max_length=100)
    university_name: str = Field(min_length=1, max_length=255)

    @field_validator("iso_code")
    @classmethod
    def _validate_iso(cls, v: str) -> str:
        v = v.strip().lower()
        if not _ISO_RE.match(v):
            raise ValueError(f"Invalid ISO 639-1/BCP-47 code: {v}")
        return v

    @field_validator("language_label", "university_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LanguageUpdate(BaseModel):
    iso_code: str | None = Field(default=None, min_length=2, max_length=10)
    language_label: str | None = Field(default=None, min_length=1, max_length=100)
    university_name: str | None = Field(default=None, min_length=1, max_length=255)

    @field_validator("iso_code")
    @classmethod
    def _validate_iso(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lower()
        if not _ISO_RE.match(v):
            raise ValueError(f"Invalid ISO 639-1/BCP-47 code: {v}")
        return v


class LanguageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    iso_code: str
    language_label: str
    university_name: str
    created_at: datetime
