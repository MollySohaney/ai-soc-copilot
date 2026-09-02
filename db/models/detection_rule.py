"""Purpose: Define the ORM model for detection rules."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.models.enums import SeverityEnum


class DetectionRule(Base):
    """Represent a detection rule used to generate alerts."""

    __tablename__ = "detection_rules"
    __table_args__ = (
        Index("ix_detection_rules_enabled", "enabled"),
        Index("ix_detection_rules_severity", "severity"),
        Index("ix_detection_rules_mitre_tactic", "mitre_tactic"),
        Index("ix_detection_rules_mitre_technique_id", "mitre_technique_id"),
        Index("ix_detection_rules_rule_type", "rule_type"),
        Index("ix_detection_rules_enabled_for_execution", "enabled_for_execution"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    query: Mapped[str] = mapped_column(String)
    structured_logic: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rule_type: Mapped[str] = mapped_column(String(20), default="single")
    version: Mapped[int] = mapped_column(Integer, default=1)
    lookback_window_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    schedule_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_events_scanned: Mapped[int] = mapped_column(Integer, default=10000)
    suppression_window_seconds: Mapped[int] = mapped_column(Integer, default=0)
    enabled_for_execution: Mapped[bool] = mapped_column(Boolean, default=False)
    severity: Mapped[SeverityEnum] = mapped_column(Enum(SeverityEnum, native_enum=False))
    risk_score: Mapped[int | None] = mapped_column(nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    mitre_tactic: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mitre_technique_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mitre_technique_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    versions = relationship("DetectionRuleVersion", back_populates="rule", cascade="all, delete-orphan")
    detection_runs = relationship("DetectionRun", back_populates="rule")
    generated_alerts = relationship("Alert", back_populates="detection_rule")


class DetectionRuleVersion(Base):
    """Immutable snapshot of the logic and settings used by one rule version."""

    __tablename__ = "detection_rule_versions"
    __table_args__ = (
        UniqueConstraint("detection_rule_id", "version", name="uq_detection_rule_versions_rule_version"),
        Index("ix_detection_rule_versions_rule_id", "detection_rule_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    detection_rule_id: Mapped[int] = mapped_column(ForeignKey("detection_rules.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    rule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    structured_logic: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    legacy_query: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    rule = relationship("DetectionRule", back_populates="versions")
