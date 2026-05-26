"""Pydantic schemas for runs and results."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.run import RunStatus, RunTrigger


class RunCreate(BaseModel):
    search_id: UUID
    # When True (default) AND the search uses search_window="last", URLs
    # already returned by previous completed runs of the same search within
    # the engine's DEDUPE_WINDOW_DAYS are suppressed. See revision_brief_v2.4
    # item 4b — this is a property of *this run*, deliberately not stored on
    # Search.config so toggling it does not edit the saved search.
    deduplicate: bool = True


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
    # Affiliation context — only meaningful when the run was performed under
    # a university (see revision_brief_v2.2.md §8.3 snapshot rule). The
    # performer-email field is what the Run History "performed by" column
    # surfaces to other members of the affiliation.
    user_id: UUID | None = None
    university_id: UUID | None = None
    performed_by_email: str | None = None


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


class BulkDeleteRequest(BaseModel):
    run_ids: list[UUID]
