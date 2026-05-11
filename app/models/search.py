"""Search and SearchTerm models — a Search groups a name, terms-per-language, and outlets."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Search(Base):
    __tablename__ = "searches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="searches")
    terms = relationship("SearchTerm", back_populates="search", cascade="all, delete-orphan")
    outlet_links = relationship(
        "SearchOutletLink", back_populates="search", cascade="all, delete-orphan"
    )
    runs = relationship("Run", back_populates="search", cascade="all, delete-orphan")


class SearchTerm(Base):
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
