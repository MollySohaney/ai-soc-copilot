"""Purpose: Persist append-only, evidence-grounded AI analysis attempts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class AIAnalysis(Base):
    """Represent one immutable AI analysis attempt scoped to an alert or case."""

    __tablename__ = "ai_analyses"
    __table_args__ = (
        CheckConstraint(
            "alert_id IS NOT NULL OR case_id IS NOT NULL",
            name="ck_ai_analyses_has_scope",
        ),
        Index("ix_ai_analyses_alert_id_created_at", "alert_id", "created_at"),
        Index("ix_ai_analyses_case_id_created_at", "case_id", "created_at"),
        Index("ix_ai_analyses_status", "status"),
        Index("ix_ai_analyses_analysis_type", "analysis_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_type: Mapped[str] = mapped_column(String(100), nullable=False)
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True)
    case_id: Mapped[int | None] = mapped_column(ForeignKey("cases.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), nullable=False)
    response_schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    evidence_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rate_limit_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    alert = relationship("Alert")
    case = relationship("Case")


@event.listens_for(AIAnalysis, "before_update")
def _reject_analysis_update(mapper, connection, target) -> None:  # noqa: ANN001
    """Prevent historical analysis records from being changed."""
    raise ValueError("AIAnalysis records are immutable")


@event.listens_for(AIAnalysis, "before_delete")
def _reject_analysis_delete(mapper, connection, target) -> None:  # noqa: ANN001
    """Prevent historical analysis records from being deleted."""
    raise ValueError("AIAnalysis records are immutable")
