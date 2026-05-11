"""Outlet model and the Search ↔ Outlet link table."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Outlet(Base):
    __tablename__ = "outlets"
    __table_args__ = (UniqueConstraint("user_id", "domain", name="uq_outlet_user_domain"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    keyword_langs: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="outlets")
    search_links = relationship(
        "SearchOutletLink", back_populates="outlet", cascade="all, delete-orphan"
    )


class SearchOutletLink(Base):
    __tablename__ = "search_outlet_links"

    search_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("searches.id", ondelete="CASCADE"), primary_key=True
    )
    outlet_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("outlets.id", ondelete="CASCADE"), primary_key=True
    )

    search = relationship("Search", back_populates="outlet_links")
    outlet = relationship("Outlet", back_populates="search_links")
