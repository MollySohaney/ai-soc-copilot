"""Purpose: Define ORM models for telemetry ingestion runs and checkpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class IngestionRun(Base):
    """Represent one bounded execution of a telemetry ingestion source."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_provider", "provider"),
        Index("ix_ingestion_runs_source_name", "source_name"),
        Index("ix_ingestion_runs_status", "status"),
        Index("ix_ingestion_runs_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    source_name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(50), default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checkpoint_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    checkpoint_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    fetched_count: Mapped[int] = mapped_column(default=0)
    normalized_count: Mapped[int] = mapped_column(default=0)
    persisted_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    warning_count: Mapped[int] = mapped_column(default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)

    events = relationship("Event", back_populates="ingestion_run")


class IngestionCheckpoint(Base):
    """Represent restart state for one configured telemetry ingestion source."""

    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (
        UniqueConstraint("provider", "source_name", name="uq_ingestion_checkpoints_provider_source"),
        Index("ix_ingestion_checkpoints_provider", "provider"),
        Index("ix_ingestion_checkpoints_source_name", "source_name"),
        Index("ix_ingestion_checkpoints_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(100))
    source_name: Mapped[str] = mapped_column(String(255))
    checkpoint: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingestion_runs.id"), nullable=True
    )

    last_run = relationship("IngestionRun")
