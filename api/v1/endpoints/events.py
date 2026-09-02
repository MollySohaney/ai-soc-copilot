"""Purpose: Expose read endpoints for telemetry events."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.schemas.event import EventRead, PaginatedEvents
from api.validation import PositiveId
from db.models.event import Event
from db.session import get_db

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=PaginatedEvents)
def list_events(
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedEvents:
    """List telemetry events, paginated and sorted by most recent first.

    Args:
        page: The 1-indexed page number to return.
        page_size: The number of events per page.
        db: The database session dependency.

    Returns:
        A page of telemetry events along with pagination metadata.
    """
    total = db.scalar(select(func.count()).select_from(Event)) or 0

    stmt = (
        select(Event)
        .order_by(Event.timestamp.desc(), Event.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = db.scalars(stmt).all()

    total_pages = math.ceil(total / page_size) if total else 0

    return PaginatedEvents(
        items=[EventRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{event_id}", response_model=EventRead)
def get_event(event_id: PositiveId, db: Session = Depends(get_db)) -> Event:
    """Retrieve a single telemetry event by its primary key.

    Args:
        event_id: The integer primary key of the event.
        db: The database session dependency.

    Returns:
        The matching telemetry event.

    Raises:
        HTTPException: If no event with the given id exists.
    """
    event = db.get(Event, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
