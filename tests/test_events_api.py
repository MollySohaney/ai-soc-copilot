"""Purpose: Verify the /events API endpoints against the seeded demo dataset."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models.event import Event

NONEXISTENT_ID = 99999


def test_list_events_default_page_shape(client: TestClient) -> None:
    """The default listing paginates seeded events with the expected shape."""
    response = client.get("/api/v1/events")

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert 50 <= body["total"] <= 100
    assert len(body["items"]) == 20
    assert body["total_pages"] == -(-body["total"] // 20)


def test_list_events_pagination_returns_disjoint_slices(client: TestClient) -> None:
    """page=2 returns a different slice of events than page 1."""
    page1 = client.get("/api/v1/events", params={"page": 1, "page_size": 10}).json()
    page2 = client.get("/api/v1/events", params={"page": 2, "page_size": 10}).json()

    ids_page1 = {item["id"] for item in page1["items"]}
    ids_page2 = {item["id"] for item in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_list_events_oversized_page_size_is_rejected(client: TestClient) -> None:
    """A page_size above the allowed maximum of 100 is rejected with 422."""
    response = client.get("/api/v1/events", params={"page_size": 101})

    assert response.status_code == 422


def test_get_event_by_id(client: TestClient, db_session: Session) -> None:
    """Retrieving an event by its id returns 200 with the matching record."""
    event = db_session.query(Event).filter_by(event_id="evt-signal-brute-01").one()

    response = client.get(f"/api/v1/events/{event.id}")

    assert response.status_code == 200
    assert response.json()["event_id"] == "evt-signal-brute-01"


def test_get_event_by_id_not_found(client: TestClient) -> None:
    """Retrieving a nonexistent event id returns 404."""
    response = client.get(f"/api/v1/events/{NONEXISTENT_ID}")

    assert response.status_code == 404
