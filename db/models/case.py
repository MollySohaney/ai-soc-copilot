"""Purpose: Define the ORM model for investigation cases."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.enums import CasePriorityEnum, CaseStatusEnum


class Case(Base):
    """Represent an investigation case grouping related alerts."""

    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_status", "status"),
        Index("ix_cases_priority", "priority"),
        Index("ix_cases_assignee", "assignee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    case_number: Mapped[str] = mapped_column(String(50), unique=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[CaseStatusEnum] = mapped_column(
        Enum(CaseStatusEnum, native_enum=False), default=CaseStatusEnum.OPEN
    )
    priority: Mapped[CasePriorityEnum] = mapped_column(
        Enum(CasePriorityEnum, native_enum=False), default=CasePriorityEnum.MEDIUM
    )
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    case_alerts = relationship("CaseAlert", back_populates="case", cascade="all, delete-orphan")
    activities = relationship(
        "CaseActivity", cascade="all, delete-orphan", order_by="CaseActivity.created_at"
    )
