"""Purpose: Provide typed client functions for the alert endpoints."""

from __future__ import annotations

from datetime import datetime

import httpx

from api.schemas.alert import AlertEventsRead, AlertRead, PaginatedAlerts
from api_client.http import _request, clean_params, get_default_client
from db.models.enums import AlertStatusEnum, SeverityEnum


def list_alerts(
    *,
    severity: SeverityEnum | None = None,
    status: AlertStatusEnum | None = None,
    source: str | None = None,
    hostname: str | None = None,
    username: str | None = None,
    mitre_tactic: str | None = None,
    mitre_technique_id: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
    client: httpx.Client | None = None,
) -> PaginatedAlerts:
    """List alerts, filtered and paginated, sorted by most recently created first.

    Args:
        severity: Filter alerts by exact severity.
        status: Filter alerts by exact triage status.
        source: Filter alerts by exact source, case-insensitive.
        hostname: Filter alerts by exact hostname, case-insensitive.
        username: Filter alerts by exact username, case-insensitive.
        mitre_tactic: Filter alerts by exact MITRE tactic, case-insensitive.
        mitre_technique_id: Filter alerts by exact MITRE technique id, case-insensitive.
        start_time: Include only alerts first seen at or after this time.
        end_time: Include only alerts first seen at or before this time.
        q: Free-text search across the alert title and description.
        page: The 1-indexed page number to return.
        page_size: The number of alerts per page.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        A page of alerts along with pagination metadata.
    """
    params = clean_params(
        severity=severity.value if severity is not None else None,
        status=status.value if status is not None else None,
        source=source,
        hostname=hostname,
        username=username,
        mitre_tactic=mitre_tactic,
        mitre_technique_id=mitre_technique_id,
        start_time=start_time.isoformat() if start_time is not None else None,
        end_time=end_time.isoformat() if end_time is not None else None,
        q=q,
        page=page,
        page_size=page_size,
    )
    response = _request(client or get_default_client(), "GET", "/alerts", params=params)
    return PaginatedAlerts.model_validate(response.json())


def get_alert(alert_id: int, *, client: httpx.Client | None = None) -> AlertRead:
    """Retrieve a single alert by its primary key.

    Args:
        alert_id: The integer primary key of the alert.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The matching alert.
    """
    response = _request(client or get_default_client(), "GET", f"/alerts/{alert_id}")
    return AlertRead.model_validate(response.json())


def update_alert(
    alert_id: int,
    *,
    status: AlertStatusEnum | None = None,
    risk_score: int | None = None,
    client: httpx.Client | None = None,
) -> AlertRead:
    """Apply a partial update to an alert.

    Args:
        alert_id: The integer primary key of the alert.
        status: The new triage status, if changing it.
        risk_score: The new risk score, if changing it.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The updated alert.
    """
    payload = clean_params(
        status=status.value if status is not None else None,
        risk_score=risk_score,
    )
    response = _request(
        client or get_default_client(), "PATCH", f"/alerts/{alert_id}", json=payload
    )
    return AlertRead.model_validate(response.json())


def get_alert_events(alert_id: int, *, client: httpx.Client | None = None) -> AlertEventsRead:
    """List the telemetry events linked to an alert.

    Args:
        alert_id: The integer primary key of the alert.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The events linked to the alert, empty if none are linked.
    """
    response = _request(client or get_default_client(), "GET", f"/alerts/{alert_id}/events")
    return AlertEventsRead.model_validate(response.json())
