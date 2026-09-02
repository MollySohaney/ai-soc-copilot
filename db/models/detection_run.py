"""Purpose: Define the ORM model for detection rule executions."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class DetectionRun(Base):
    """Represent one bounded execution of a detection rule."""

    __tablename__ = "detection_runs"
    __table_args__ = (
        Index("ix_detection_runs_rule_id", "detection_rule_id"),
        Index("ix_detection_runs_started_at", "started_at"),
        Index("ix_detection_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    detection_rule_id: Mapped[int] = mapped_column(ForeignKey("detection_rules.id"), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running")
    events_scanned: Mapped[int] = mapped_column(Integer, default=0)
    alerts_created: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)

    rule = relationship("DetectionRule", back_populates="detection_runs")
    alerts = relationship("Alert", back_populates="detection_run")
