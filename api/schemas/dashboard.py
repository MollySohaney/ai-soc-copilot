"""Purpose: Define response DTOs for dashboard analytics endpoints."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from api.schemas.alert import AlertRead
from db.models.enums import SeverityEnum


class DashboardSummary(BaseModel):
    """Represent the aggregate metrics shown on the dashboard summary."""

    total_alerts: int
    new_alerts: int
    critical_alerts: int
    in_progress_alerts: int
    open_cases: int
    mean_time_to_acknowledge_minutes: float | None
    alert_change_pct: float | None


class AlertTrendPoint(BaseModel):
    """Represent the alert count for a single day."""

    date: date
    count: int


class AlertTrendsResponse(BaseModel):
    """Represent a series of daily alert counts."""

    items: list[AlertTrendPoint]


class SeverityDistributionEntry(BaseModel):
    """Represent the alert count for a single severity level."""

    severity: SeverityEnum
    count: int


class SeverityDistributionResponse(BaseModel):
    """Represent the alert count broken down by severity."""

    items: list[SeverityDistributionEntry]


class RecentAlertsResponse(BaseModel):
    """Represent the most recently created alerts."""

    items: list[AlertRead]
