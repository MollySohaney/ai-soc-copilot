"""Purpose: Expose aggregate analytics endpoints for the SOC dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.dashboard import (
    AlertTrendPoint,
    AlertTrendsResponse,
    DashboardSummary,
    RecentAlertsResponse,
    SeverityDistributionEntry,
    SeverityDistributionResponse,
)
from api.schemas.alert import AlertRead
from db.models.alert import Alert
from db.models.case import Case
from db.models.enums import AlertStatusEnum, CaseStatusEnum, SeverityEnum
from db.session import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

_OPEN_CASE_STATUSES = (CaseStatusEnum.OPEN, CaseStatusEnum.IN_PROGRESS)


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    as_of: datetime | None = None,
    period_days: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Compute the aggregate metrics shown on the dashboard summary.

    Args:
        as_of: The reference time for period comparisons; defaults to now.
        period_days: The length, in days, of the current and prior comparison periods.
        db: The database session dependency.

    Returns:
        The current alert and case counts, plus period-over-period alert change.
    """
    reference = as_of if as_of is not None else datetime.now(timezone.utc)

    total_alerts = db.scalar(select(func.count()).select_from(Alert)) or 0
    new_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.status == AlertStatusEnum.NEW)
    ) or 0
    critical_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.severity == SeverityEnum.CRITICAL)
    ) or 0
    in_progress_alerts = db.scalar(
        select(func.count()).select_from(Alert).where(Alert.status == AlertStatusEnum.IN_PROGRESS)
    ) or 0
    open_cases = db.scalar(
        select(func.count()).select_from(Case).where(Case.status.in_(_OPEN_CASE_STATUSES))
    ) or 0

    current_start = reference - timedelta(days=period_days)
    previous_start = current_start - timedelta(days=period_days)

    current_count = db.scalar(
        select(func.count())
        .select_from(Alert)
        .where(Alert.created_at >= current_start, Alert.created_at < reference)
    ) or 0
    previous_count = db.scalar(
        select(func.count())
        .select_from(Alert)
        .where(Alert.created_at >= previous_start, Alert.created_at < current_start)
    ) or 0

    alert_change_pct = (
        None if previous_count == 0 else ((current_count - previous_count) / previous_count) * 100
    )

    return DashboardSummary(
        total_alerts=total_alerts,
        new_alerts=new_alerts,
        critical_alerts=critical_alerts,
        in_progress_alerts=in_progress_alerts,
        open_cases=open_cases,
        # Alert has no acknowledged_at/acknowledged_by field in the schema, so mean
        # time-to-acknowledge cannot be computed. Returning a proxy (e.g. from
        # updated_at) would misrepresent triage speed, so this is always None.
        mean_time_to_acknowledge_minutes=None,
        alert_change_pct=alert_change_pct,
    )


@router.get("/alert-trends", response_model=AlertTrendsResponse)
def get_alert_trends(
    as_of: datetime | None = None,
    days: int = Query(default=14, ge=1),
    db: Session = Depends(get_db),
) -> AlertTrendsResponse:
    """Compute the daily alert count over a trailing window of days.

    Buckets are computed in Python rather than via SQL date-truncation functions,
    since the date functions differ between SQLite (used in tests) and Postgres
    (used in production).

    Args:
        as_of: The reference time marking the end of the window; defaults to now.
        days: The number of trailing days to include.
        db: The database session dependency.

    Returns:
        A zero-filled daily alert count for every day in the window.
    """
    reference = as_of if as_of is not None else datetime.now(timezone.utc)
    end_date = reference.date()
    start_date = end_date - timedelta(days=days - 1)
    range_start = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
    range_end = range_start + timedelta(days=days)

    created_at_values = db.scalars(
        select(Alert.created_at).where(
            Alert.created_at >= range_start, Alert.created_at < range_end
        )
    ).all()

    counts: Counter[date] = Counter()
    for created_at in created_at_values:
        if created_at.tzinfo is None:
            bucket = created_at.date()
        else:
            bucket = created_at.astimezone(timezone.utc).date()
        counts[bucket] += 1

    items = [
        AlertTrendPoint(date=day, count=counts.get(day, 0))
        for day in (start_date + timedelta(days=offset) for offset in range(days))
    ]

    return AlertTrendsResponse(items=items)


@router.get("/severity-distribution", response_model=SeverityDistributionResponse)
def get_severity_distribution(
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    db: Session = Depends(get_db),
) -> SeverityDistributionResponse:
    """Compute the alert count broken down by severity.

    Args:
        start_time: Include only alerts first seen at or after this time.
        end_time: Include only alerts first seen at or before this time.
        db: The database session dependency.

    Returns:
        The alert count for every severity level, sorted low to critical, with
        zero-count entries filled in for severities that had no matches.
    """
    filters = []
    if start_time is not None:
        filters.append(Alert.first_seen >= start_time)
    if end_time is not None:
        filters.append(Alert.first_seen <= end_time)

    stmt = (
        select(Alert.severity, func.count())
        .where(*filters)
        .group_by(Alert.severity)
    )
    counts = {severity: count for severity, count in db.execute(stmt).all()}

    items = [
        SeverityDistributionEntry(severity=severity, count=counts.get(severity, 0))
        for severity in (
            SeverityEnum.LOW,
            SeverityEnum.MEDIUM,
            SeverityEnum.HIGH,
            SeverityEnum.CRITICAL,
        )
    ]

    return SeverityDistributionResponse(items=items)


@router.get("/recent-alerts", response_model=RecentAlertsResponse)
def get_recent_alerts(
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
) -> RecentAlertsResponse:
    """Retrieve the most recently created alerts.

    Args:
        limit: The maximum number of alerts to return.
        db: The database session dependency.

    Returns:
        The most recent alerts, most recently created first.
    """
    stmt = select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
    items = db.scalars(stmt).all()

    return RecentAlertsResponse(items=[AlertRead.model_validate(item) for item in items])
