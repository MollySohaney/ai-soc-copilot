"""Purpose: Define the ORM model for the case activity timeline."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CaseActivity(Base):
    """Represent a single timeline entry recorded against a case."""

    __tablename__ = "case_activities"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"), index=True)
    activity_type: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(String)
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
