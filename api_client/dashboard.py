"""Purpose: Provide typed client functions for the dashboard analytics endpoints."""

from __future__ import annotations

from datetime import datetime

import httpx

from api.schemas.dashboard import (
    AlertTrendsResponse,
    DashboardSummary,
    RecentAlertsResponse,
    SeverityDistributionResponse,
)
from api_client.http import _request, clean_params, get_default_client


def get_dashboard_summary(
    *,
    as_of: datetime | None = None,
    period_days: int = 1,
    client: httpx.Client | None = None,
) -> DashboardSummary:
    """Compute the aggregate metrics shown on the dashboard summary.

    Args:
        as_of: The reference time for period comparisons; defaults to now.
        period_days: The length, in days, of the current and prior comparison periods.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The current alert and case counts, plus period-over-period alert change.
    """
    params = clean_params(
        as_of=as_of.isoformat() if as_of is not None else None,
        period_days=period_days,
    )
    response = _request(client or get_default_client(), "GET", "/dashboard/summary", params=params)
    return DashboardSummary.model_validate(response.json())


def get_alert_trends(
    *,
    as_of: datetime | None = None,
    days: int = 14,
    client: httpx.Client | None = None,
) -> AlertTrendsResponse:
    """Compute the daily alert count over a trailing window of days.

    Args:
        as_of: The reference time marking the end of the window; defaults to now.
        days: The number of trailing days to include.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        A zero-filled daily alert count for every day in the window.
    """
    params = clean_params(as_of=as_of.isoformat() if as_of is not None else None, days=days)
    response = _request(
        client or get_default_client(), "GET", "/dashboard/alert-trends", params=params
    )
    return AlertTrendsResponse.model_validate(response.json())


def get_severity_distribution(
    *,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    client: httpx.Client | None = None,
) -> SeverityDistributionResponse:
    """Compute the alert count broken down by severity.

    Args:
        start_time: Include only alerts first seen at or after this time.
        end_time: Include only alerts first seen at or before this time.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The alert count for every severity level, sorted low to critical, with
        zero-count entries filled in for severities that had no matches.
    """
    params = clean_params(
        start_time=start_time.isoformat() if start_time is not None else None,
        end_time=end_time.isoformat() if end_time is not None else None,
    )
    response = _request(
        client or get_default_client(), "GET", "/dashboard/severity-distribution", params=params
    )
    return SeverityDistributionResponse.model_validate(response.json())


def get_recent_alerts(
    *, limit: int = 5, client: httpx.Client | None = None
) -> RecentAlertsResponse:
    """Retrieve the most recently created alerts.

    Args:
        limit: The maximum number of alerts to return.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The most recent alerts, most recently created first.
    """
    params = clean_params(limit=limit)
    response = _request(
        client or get_default_client(), "GET", "/dashboard/recent-alerts", params=params
    )
    return RecentAlertsResponse.model_validate(response.json())
