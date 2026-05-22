"""UniversityLanguage model — per-user language definitions for the university name search option."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UniversityLanguage(Base):
    """Per-tenant language definition.

    When ``university_id`` is null the row is private to ``user_id``
    (unaffiliated behaviour). When set, the row is *shared* across all
    members of that university — any member may view or edit it.

    The uniqueness constraint enforces "no duplicate ISO per scope": one
    English entry per user when unaffiliated, one English entry per
    university when affiliated. PostgreSQL treats nulls as distinct under
    UNIQUE, which gives us exactly that semantic without partial indexes.
    """
    __tablename__ = "university_languages"
    __table_args__ = (
        UniqueConstraint("user_id", "iso_code", name="uq_university_languages_user_iso"),
        UniqueConstraint(
            "university_id", "iso_code", name="uq_university_languages_uni_iso"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    university_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("universities.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    iso_code: Mapped[str] = mapped_column(String(10), nullable=False)
    university_name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="languages")
