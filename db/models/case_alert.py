"""Purpose: Define the association model linking cases to alerts."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class CaseAlert(Base):
    """Represent the many-to-many link between a case and an alert."""

    __tablename__ = "case_alerts"
    __table_args__ = (UniqueConstraint("case_id", "alert_id", name="uq_case_alerts_case_id_alert_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("cases.id"))
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.id"))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
