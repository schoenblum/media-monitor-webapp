"""Search model with JSONB config column.

The config column stores the complete search configuration:
  {
    "search_window": "last" | "hours" | "range",
    "fallback_hours": 72,
    "date_from": "YYYY-MM-DD",   # only meaningful when search_window == "range"
    "date_to":   "YYYY-MM-DD",   # optional; empty = up to today
    "terms_pages": 1,            # section-level page count for the combined terms query
    "terms": [{"id": str, "text": str, "operator": null|"AND"|"OR"|"NOT"}],
    "doi": {"text": str, "pages": int},
    "university_name": {"enabled": bool, "language_ids": [str], "pages": int},
    "outlets": {"enabled": bool, "outlet_ids": [str]}
  }
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


DEFAULT_SEARCH_CONFIG: dict = {
    "search_window": "last",
    "fallback_hours": 72,
    "date_from": "",
    "date_to": "",
    "terms_pages": 1,
    "terms": [],
    "doi": {"text": "", "pages": 1},
    "university_name": {"enabled": False, "language_ids": [], "pages": 1},
    "outlets": {"enabled": False, "outlet_ids": []},
    # v2.4 item 7 — manual by default. The scheduler ignores this until the
    # user flips mode to "auto" on the Searches form.
    "schedule": {
        "mode": "manual",
        "interval_hours": 24,
        "start_time": "08:00",
        "timezone": "Asia/Tokyo",
    },
}


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="searches")
    runs = relationship("Run", back_populates="search", cascade="all, delete-orphan")
