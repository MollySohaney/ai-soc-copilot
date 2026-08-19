"""Purpose: Provide typed client functions for the telemetry event endpoints."""

from __future__ import annotations

import httpx

from api.schemas.event import EventRead, PaginatedEvents
from api_client.http import _request, clean_params, get_default_client


def list_events(
    *,
    page: int = 1,
    page_size: int = 20,
    client: httpx.Client | None = None,
) -> PaginatedEvents:
    """List telemetry events, paginated and sorted by most recent first.

    Args:
        page: The 1-indexed page number to return.
        page_size: The number of events per page.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        A page of telemetry events along with pagination metadata.
    """
    params = clean_params(page=page, page_size=page_size)
    response = _request(client or get_default_client(), "GET", "/events", params=params)
    return PaginatedEvents.model_validate(response.json())


def get_event(event_id: int, *, client: httpx.Client | None = None) -> EventRead:
    """Retrieve a single telemetry event by its primary key.

    Args:
        event_id: The integer primary key of the event.
        client: The httpx client to issue the request with; defaults to the
            shared client built from application settings.

    Returns:
        The matching telemetry event.
    """
    response = _request(client or get_default_client(), "GET", f"/events/{event_id}")
    return EventRead.model_validate(response.json())
