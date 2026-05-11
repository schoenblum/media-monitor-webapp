"""Pydantic schemas for runs and results."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.run import RunStatus, RunTrigger


class RunCreate(BaseModel):
    search_id: UUID


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    search_id: UUID
    triggered_by: RunTrigger
    status: RunStatus
    started_at: datetime
    completed_at: datetime | None
    api_calls_used: int
    error_message: str | None
    search_name: str | None = None
    result_count: int = 0


class ResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    run_id: UUID
    outlet_name: str
    title: str
    url: str
    display_source: str
    snippet: str
    date_extracted: str
    keyword_used: str
    search_lang: str
    detected_lang: str
    detected_lang_name: str
    is_selected: bool


class ResultSelectionUpdate(BaseModel):
    result_ids: list[UUID]
    selected: bool


class ResultsPage(BaseModel):
    items: list[ResultOut]
    total: int
    page: int
    page_size: int
