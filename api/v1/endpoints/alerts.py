"""Purpose: Expose read, filter, and update endpoints for alerts."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from api.schemas.alert import AlertEventsRead, AlertRead, AlertUpdate, PaginatedAlerts
from api.schemas.event import EventRead
from db.models.alert import Alert, alert_event
from db.models.enums import AlertStatusEnum, SeverityEnum
from db.models.event import Event
from db.session import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=PaginatedAlerts)
def list_alerts(
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
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
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
        db: The database session dependency.

    Returns:
        A page of alerts along with pagination metadata.
    """
    filters = []
    if severity is not None:
        filters.append(Alert.severity == severity)
    if status is not None:
        filters.append(Alert.status == status)
    if source is not None:
        filters.append(func.lower(Alert.source) == source.lower())
    if hostname is not None:
        filters.append(func.lower(Alert.hostname) == hostname.lower())
    if username is not None:
        filters.append(func.lower(Alert.username) == username.lower())
    if mitre_tactic is not None:
        filters.append(func.lower(Alert.mitre_tactic) == mitre_tactic.lower())
    if mitre_technique_id is not None:
        filters.append(func.lower(Alert.mitre_technique_id) == mitre_technique_id.lower())
    if start_time is not None:
        filters.append(Alert.first_seen >= start_time)
    if end_time is not None:
        filters.append(Alert.first_seen <= end_time)
    if q is not None:
        pattern = f"%{q}%"
        filters.append(or_(Alert.title.ilike(pattern), Alert.description.ilike(pattern)))

    count_stmt = select(func.count()).select_from(Alert).where(*filters)
    total = db.scalar(count_stmt) or 0

    stmt = (
        select(Alert)
        .where(*filters)
        .order_by(Alert.created_at.desc(), Alert.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    total_pages = math.ceil(total / page_size) if total else 0

    return PaginatedAlerts(
        items=[AlertRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> Alert:
    """Retrieve a single alert by its primary key.

    Args:
        alert_id: The integer primary key of the alert.
        db: The database session dependency.

    Returns:
        The matching alert.

    Raises:
        HTTPException: If no alert with the given id exists.
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert


@router.patch("/{alert_id}", response_model=AlertRead)
def update_alert(alert_id: int, payload: AlertUpdate, db: Session = Depends(get_db)) -> Alert:
    """Apply a partial update to an alert.

    Args:
        alert_id: The integer primary key of the alert.
        payload: The fields to update; unset fields are left unchanged.
        db: The database session dependency.

    Returns:
        The updated alert.

    Raises:
        HTTPException: If no alert with the given id exists.
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(alert, field, value)
    if updates:
        alert.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alert)
    return alert


@router.get("/{alert_id}/events", response_model=AlertEventsRead)
def list_alert_events(alert_id: int, db: Session = Depends(get_db)) -> AlertEventsRead:
    """List the telemetry events linked to an alert.

    Args:
        alert_id: The integer primary key of the alert.
        db: The database session dependency.

    Returns:
        The events linked to the alert, empty if none are linked.

    Raises:
        HTTPException: If no alert with the given id exists.
    """
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")

    stmt = (
        select(Event)
        .join(alert_event, alert_event.c.event_id == Event.id)
        .where(alert_event.c.alert_id == alert_id)
        .order_by(Event.timestamp.desc(), Event.id.desc())
    )
    events = db.scalars(stmt).all()

    return AlertEventsRead(
        items=[EventRead.model_validate(event) for event in events],
        total=len(events),
    )
