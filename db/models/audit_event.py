"""Purpose: Persist immutable, actor-attributed security audit events."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, event
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class AuditEvent(Base):
    """Represent one append-only security-relevant action or attempt."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_event_id", "event_id", unique=True),
        Index("ix_audit_events_occurred_at", "occurred_at"),
        Index("ix_audit_events_actor_user_id_occurred_at", "actor_user_id", "occurred_at"),
        Index("ix_audit_events_action_occurred_at", "action", "occurred_at"),
        Index("ix_audit_events_target_occurred_at", "target_type", "target_id", "occurred_at"),
        Index("ix_audit_events_outcome_occurred_at", "outcome", "occurred_at"),
        Index("ix_audit_events_request_id", "request_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    source_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


def _reject_audit_mutation(*_args, **_kwargs) -> None:  # noqa: ANN002, ANN003
    raise ValueError("Audit events are append-only.")


event.listen(AuditEvent, "before_update", _reject_audit_mutation)
event.listen(AuditEvent, "before_delete", _reject_audit_mutation)
