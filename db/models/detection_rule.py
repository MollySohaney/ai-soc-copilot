"""Purpose: Define the ORM model for detection rules."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Index, String
from sqlalchemy.orm import Mapped, mapped_column

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
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    query: Mapped[str] = mapped_column(String)
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
