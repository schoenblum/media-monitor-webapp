"""Run model — one search execution producing zero or more Results."""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    complete = "complete"
    failed = "failed"
    # v2.4 item 5/7 — a scheduled fire that could not proceed (no Google
    # credentials, empty config, quota exhausted). Distinct from `failed` so
    # the UI can render it calmly rather than as an error.
    skipped = "skipped"


class RunTrigger(str, enum.Enum):
    manual = "manual"
    webhook = "webhook"
    # v2.4 item 7 — created by the in-process APScheduler from a search whose
    # config.schedule.mode == "auto".
    scheduled = "scheduled"


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Snapshot of the performing user's affiliation at run-creation time.
    # Null = the run was performed while the user was unaffiliated. Runs stay
    # with the university they were performed under and do NOT migrate when
    # a user is later reassigned (see revision_brief_v2.2.md §8.3).
    university_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("universities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    triggered_by: Mapped[RunTrigger] = mapped_column(
        Enum(RunTrigger, name="run_trigger"), default=RunTrigger.manual, nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, name="run_status"), default=RunStatus.pending, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    api_calls_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    user = relationship("User", back_populates="runs")
    search = relationship("Search", back_populates="runs")
    results = relationship("Result", back_populates="run", cascade="all, delete-orphan")
