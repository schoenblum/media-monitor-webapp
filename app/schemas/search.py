"""Pydantic schemas for searches — config-based model."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Search config sub-schemas
# ---------------------------------------------------------------------------


class SearchTermConfig(BaseModel):
    id: str = ""
    text: str = ""
    operator: Literal["AND", "OR", "NOT"] | None = None
    pages: int = Field(default=1, ge=1, le=10)


class DoiConfig(BaseModel):
    text: str = ""
    pages: int = Field(default=1, ge=1, le=10)


class UniversityNameConfig(BaseModel):
    enabled: bool = False
    language_ids: list[str] = []


class OutletsConfig(BaseModel):
    enabled: bool = False
    outlet_ids: list[str] = []


class SearchConfig(BaseModel):
    search_window: Literal["last", "hours"] = "last"
    fallback_hours: int = Field(default=72, ge=1, le=8760)
    terms: list[SearchTermConfig] = []
    doi: DoiConfig = Field(default_factory=DoiConfig)
    university_name: UniversityNameConfig = Field(default_factory=UniversityNameConfig)
    outlets: OutletsConfig = Field(default_factory=OutletsConfig)


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class SearchCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    is_default: bool = False
    config: SearchConfig = Field(default_factory=SearchConfig)


class SearchUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    is_default: bool | None = None
    config: SearchConfig | None = None


class SearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    is_default: bool
    config: dict
    created_at: datetime
    updated_at: datetime
