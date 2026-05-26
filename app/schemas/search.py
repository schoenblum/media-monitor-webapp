"""Pydantic schemas for searches — config-based model.

NOTE: any change to this schema must be mirrored in
``frontend/src/api/types.ts`` (``SearchConfig`` + ``defaultSearchConfig()``).
"""
import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, available_timezones

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Search config sub-schemas
# ---------------------------------------------------------------------------


class SearchTermConfig(BaseModel):
    id: str = ""
    text: str = ""
    operator: Literal["AND", "OR", "NOT"] | None = None


class DoiConfig(BaseModel):
    text: str = ""
    pages: int = Field(default=1, ge=1, le=10)


class UniversityNameConfig(BaseModel):
    enabled: bool = False
    language_ids: list[str] = []
    pages: int = Field(default=1, ge=1, le=10)


class OutletsConfig(BaseModel):
    enabled: bool = False
    outlet_ids: list[str] = []


_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_CACHED_TZS: set[str] = set()


def _is_valid_timezone(tz: str) -> bool:
    global _CACHED_TZS
    if not _CACHED_TZS:
        _CACHED_TZS = available_timezones()
    if tz in _CACHED_TZS:
        return True
    # Fallback in case zoneinfo's cache doesn't list every alias on this
    # platform — try to construct the zone.
    try:
        ZoneInfo(tz)
        return True
    except Exception:
        return False


class ScheduleConfig(BaseModel):
    """Per-search schedule (v2.4 item 7).

    ``mode == "manual"`` is the existing behaviour — the search only runs when
    something else triggers it (UI button, webhook). ``mode == "auto"`` means
    the in-process APScheduler should fire it on a cadence.
    """

    mode: Literal["manual", "auto"] = "manual"
    interval_hours: int = Field(default=24, ge=1, le=8760)
    start_time: str = "08:00"
    timezone: str = "Asia/Tokyo"

    @model_validator(mode="after")
    def _validate(self) -> "ScheduleConfig":
        if not _TIME_RE.match(self.start_time or ""):
            raise ValueError("start_time must be HH:MM (24-hour).")
        if not _is_valid_timezone(self.timezone):
            raise ValueError(f"Unknown IANA timezone: {self.timezone!r}.")
        return self


def _parse_iso_date(value: str) -> date | None:
    s = (value or "").strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


class SearchConfig(BaseModel):
    search_window: Literal["last", "hours", "range"] = "last"
    fallback_hours: int = Field(default=72, ge=1, le=8760)
    date_from: str = ""
    date_to: str = ""
    terms_pages: int = Field(default=1, ge=1, le=10)
    terms: list[SearchTermConfig] = []
    doi: DoiConfig = Field(default_factory=DoiConfig)
    university_name: UniversityNameConfig = Field(default_factory=UniversityNameConfig)
    outlets: OutletsConfig = Field(default_factory=OutletsConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)

    @model_validator(mode="after")
    def _validate_range(self) -> "SearchConfig":
        # Recurring schedules and fixed calendar windows are mutually exclusive:
        # a "range" search has a hard-coded date_from/date_to and produces the
        # same results on every fire, so firing it on a timer is nonsensical.
        # Reject this combination at the schema layer so the API can't persist it.
        if self.schedule.mode == "auto" and self.search_window == "range":
            raise ValueError(
                "Scheduled (auto) runs cannot use search_window='range' — switch "
                "to 'last' or 'hours' before enabling automatic runs."
            )
        if self.search_window != "range":
            return self
        df = _parse_iso_date(self.date_from)
        if df is None:
            raise ValueError("date_from is required (YYYY-MM-DD) when search_window is 'range'.")
        if self.date_to.strip():
            dt = _parse_iso_date(self.date_to)
            if dt is None:
                raise ValueError("date_to must be YYYY-MM-DD or empty.")
            if df > dt:
                raise ValueError("date_from must be on or before date_to.")
        return self


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
