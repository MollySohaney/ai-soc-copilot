"""Purpose: Define the ORM model for raw ingested telemetry events."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class Event(Base):
    """Represent a single raw telemetry event ingested from a data source."""

    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_timestamp", "timestamp"),
        Index("ix_events_source", "source"),
        Index("ix_events_event_category", "event_category"),
        Index("ix_events_severity", "severity"),
        Index("ix_events_source_ip", "source_ip"),
        Index("ix_events_destination_ip", "destination_ip"),
        Index("ix_events_hostname", "hostname"),
        Index("ix_events_username", "username"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    source: Mapped[str] = mapped_column(String(255))
    dataset: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(50), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    source_port: Mapped[int | None] = mapped_column(nullable=True)
    destination_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    destination_port: Mapped[int | None] = mapped_column(nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    process_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    process_command_line: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_event: Mapped[dict | None] = mapped_column(JSON, nullable=True)
