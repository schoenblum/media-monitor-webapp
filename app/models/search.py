"""Search model with JSONB config column.

The config column stores the complete search configuration:
  {
    "search_window": "last" | "hours",
    "fallback_hours": 72,
    "terms": [{"id": str, "text": str, "operator": null|"AND"|"OR"|"NOT", "pages": int}],
    "doi": {"text": str, "pages": int},
    "university_name": {"enabled": bool, "language_ids": [str]},
    "outlets": {"enabled": bool, "outlet_ids": [str]}
  }

SearchTerm and the search_terms table are kept in the DB for historical data but
are no longer used by the application — all search logic reads from config.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


DEFAULT_SEARCH_CONFIG: dict = {
    "search_window": "last",
    "fallback_hours": 72,
    "terms": [],
    "doi": {"text": "", "pages": 1},
    "university_name": {"enabled": False, "language_ids": []},
    "outlets": {"enabled": False, "outlet_ids": []},
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

    # Legacy relationships — kept so Alembic sees the tables; not used in app logic.
    terms = relationship("SearchTerm", back_populates="search", cascade="all, delete-orphan")
    outlet_links = relationship(
        "SearchOutletLink", back_populates="search", cascade="all, delete-orphan"
    )


class SearchTerm(Base):
    """Legacy table — superseded by searches.config. Kept for DB-level compatibility."""
    __tablename__ = "search_terms"
    __table_args__ = (UniqueConstraint("search_id", "language_code", name="uq_term_search_lang"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), nullable=False
    )
    language_code: Mapped[str] = mapped_column(String(8), nullable=False)
    term: Mapped[str] = mapped_column(String(500), nullable=False)
    pages: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    search = relationship("Search", back_populates="terms")
