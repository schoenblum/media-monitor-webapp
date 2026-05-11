"""Result model — a single article hit from a Run."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Result(Base):
    __tablename__ = "results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    outlet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    display_source: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    date_extracted: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    keyword_used: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    search_lang: Mapped[str] = mapped_column(String(8), nullable=False, default="")
    detected_lang: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    detected_lang_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    is_selected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    run = relationship("Run", back_populates="results")
