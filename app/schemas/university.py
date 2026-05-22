"""Pydantic schemas for the universities admin surface."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UniversityCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class UniversityUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class UniversityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    member_count: int = 0


class DuplicateRunsRequest(BaseModel):
    """Optional admin action when re-assigning a user.

    Copies the user's personal run history (runs that pre-date the move) into
    the target university's pool. Originals stay where they were per the
    snapshot rule (§8.3).
    """

    user_id: UUID
    target_university_id: UUID


class DuplicateRunsReport(BaseModel):
    runs_copied: int
    results_copied: int
