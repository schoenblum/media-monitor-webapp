"""Pydantic schemas for searches and search-terms."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.default_outlets import SUPPORTED_LANGUAGES


class SearchTermIn(BaseModel):
    language_code: str
    term: str
    pages: int = Field(default=3, ge=1, le=10)
    is_enabled: bool = True

    @field_validator("language_code")
    @classmethod
    def _validate_lang(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language code: {v}")
        return v


class SearchTermOut(SearchTermIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class SearchBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False


class SearchCreate(SearchBase):
    pass


class SearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None


class SearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    is_default: bool
    created_at: datetime
    updated_at: datetime
    terms: list[SearchTermOut] = []
    outlet_ids: list[UUID] = []


class TermsReplaceRequest(BaseModel):
    terms: list[SearchTermIn]


class LinkOutletsRequest(BaseModel):
    outlet_ids: list[UUID]
