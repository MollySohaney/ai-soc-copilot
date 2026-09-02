"""Purpose: Define the ORM model for alerts and their linked events."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.enums import AlertStatusEnum, SeverityEnum

alert_event = Table(
    "alert_event",
    Base.metadata,
    Column("alert_id", Integer, ForeignKey("alerts.id"), primary_key=True),
    Column("event_id", Integer, ForeignKey("events.id"), primary_key=True),
    Column("stage", String(100), nullable=True),
)


class Alert(Base):
    """Represent an alert generated from one or more detected events."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_status", "status"),
        Index("ix_alerts_source", "source"),
        Index("ix_alerts_rule_id", "rule_id"),
        Index("ix_alerts_hostname", "hostname"),
        Index("ix_alerts_username", "username"),
        Index("ix_alerts_source_ip", "source_ip"),
        Index("ix_alerts_mitre_tactic", "mitre_tactic"),
        Index("ix_alerts_mitre_technique_id", "mitre_technique_id"),
        Index("ix_alerts_first_seen", "first_seen"),
        Index("ix_alerts_last_seen", "last_seen"),
        Index("ix_alerts_detection_rule_id", "detection_rule_id"),
        Index("ix_alerts_detection_run_id", "detection_run_id"),
        Index("ix_alerts_fingerprint", "fingerprint", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    severity: Mapped[SeverityEnum] = mapped_column(Enum(SeverityEnum, native_enum=False))
    risk_score: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[AlertStatusEnum] = mapped_column(
        Enum(AlertStatusEnum, native_enum=False), default=AlertStatusEnum.NEW
    )
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detection_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("detection_rules.id"), nullable=True
    )
    rule_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detection_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("detection_runs.id"), nullable=True
    )
    fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    rule_logic_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    match_explanation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    destination_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    mitre_tactic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mitre_technique_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mitre_technique_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    events = relationship("Event", secondary=alert_event, backref="alerts")
    detection_rule = relationship("DetectionRule", back_populates="generated_alerts")
    detection_run = relationship("DetectionRun", back_populates="alerts")
