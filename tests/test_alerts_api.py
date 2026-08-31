"""Purpose: Verify the /alerts API endpoints against the seeded demo dataset."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models.alert import Alert
from db.seed import BASE_TIME, TARGET_HOST, TARGET_USER

NONEXISTENT_ID = 99999


def _alert_id(db_session: Session, external_id: str) -> int:
    return db_session.query(Alert).filter_by(external_id=external_id).one().id


def test_list_alerts_default_page_shape(client: TestClient) -> None:
    """The default listing returns every seeded alert on a single page."""
    response = client.get("/api/v1/alerts")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 13
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1
    assert len(body["items"]) == 13


def test_list_alerts_pagination_returns_disjoint_stable_slices(client: TestClient) -> None:
    """page=2&page_size=5 returns a different, stably-ordered slice than page 1."""
    page1 = client.get("/api/v1/alerts", params={"page": 1, "page_size": 5}).json()
    page2 = client.get("/api/v1/alerts", params={"page": 2, "page_size": 5}).json()

    assert page1["total"] == 13
    assert page1["total_pages"] == 3
    assert len(page1["items"]) == 5
    assert len(page2["items"]) == 5

    ids_page1 = {item["id"] for item in page1["items"]}
    ids_page2 = {item["id"] for item in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)

    # Re-querying page 1 returns the exact same ordering (stable sort).
    page1_again = client.get("/api/v1/alerts", params={"page": 1, "page_size": 5}).json()
    assert [item["id"] for item in page1["items"]] == [item["id"] for item in page1_again["items"]]


def test_list_alerts_oversized_page_size_is_rejected(client: TestClient) -> None:
    """A page_size above the allowed maximum of 100 is rejected with 422."""
    response = client.get("/api/v1/alerts", params={"page_size": 101})

    assert response.status_code == 422


def test_filter_by_severity(client: TestClient) -> None:
    """Filtering by severity=critical returns only the two critical seeded alerts."""
    response = client.get("/api/v1/alerts", params={"severity": "critical"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["severity"] == "critical" for item in body["items"])


def test_filter_by_status(client: TestClient) -> None:
    """Filtering by status=new returns only the four seeded new alerts."""
    response = client.get("/api/v1/alerts", params={"status": "new"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 4
    assert all(item["status"] == "new" for item in body["items"])


def test_filter_by_source_hits_only_correlated_chain_alert(client: TestClient) -> None:
    """Filtering by source=correlation-engine returns only the correlated chain alert."""
    response = client.get("/api/v1/alerts", params={"source": "correlation-engine"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "ALERT-0006"


def test_filter_by_hostname(client: TestClient) -> None:
    """Filtering by hostname matches all six chain alerts on the target host."""
    response = client.get("/api/v1/alerts", params={"hostname": TARGET_HOST})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert all(item["hostname"] == TARGET_HOST for item in body["items"])


def test_filter_by_username(client: TestClient) -> None:
    """Filtering by username matches all six chain alerts for the target user."""
    response = client.get("/api/v1/alerts", params={"username": TARGET_USER})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 6
    assert all(item["username"] == TARGET_USER for item in body["items"])


def test_filter_by_mitre_tactic(client: TestClient) -> None:
    """Filtering by mitre_tactic=Persistence returns the two seeded persistence-tactic alerts."""
    response = client.get("/api/v1/alerts", params={"mitre_tactic": "Persistence"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert all(item["mitre_tactic"] == "Persistence" for item in body["items"])


def test_filter_by_mitre_technique_id(client: TestClient) -> None:
    """Filtering by mitre_technique_id=T1110 returns only the brute-force alert."""
    response = client.get("/api/v1/alerts", params={"mitre_technique_id": "T1110"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "ALERT-0001"


def test_filter_by_first_seen_window(client: TestClient) -> None:
    """start_time/end_time bounds first_seen to the brute-force, login, and chain alerts."""
    start_time = BASE_TIME.isoformat()
    end_time = (BASE_TIME.replace(minute=5)).isoformat()

    response = client.get(
        "/api/v1/alerts", params={"start_time": start_time, "end_time": end_time}
    )

    assert response.status_code == 200
    body = response.json()
    external_ids = {item["external_id"] for item in body["items"]}
    assert external_ids == {"ALERT-0001", "ALERT-0002", "ALERT-0006"}


def test_filter_by_text_search(client: TestClient) -> None:
    """q performs a free-text search over title/description, matching a unique keyword."""
    response = client.get("/api/v1/alerts", params={"q": "svc-backup2"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["external_id"] == "ALERT-0004"


def test_get_alert_by_id(client: TestClient, db_session: Session) -> None:
    """Retrieving an alert by its id returns 200 with the matching record."""
    alert_id = _alert_id(db_session, "ALERT-0001")

    response = client.get(f"/api/v1/alerts/{alert_id}")

    assert response.status_code == 200
    assert response.json()["external_id"] == "ALERT-0001"


def test_get_alert_by_id_not_found(client: TestClient) -> None:
    """Retrieving a nonexistent alert id returns 404."""
    response = client.get(f"/api/v1/alerts/{NONEXISTENT_ID}")

    assert response.status_code == 404


def test_get_alert_events_returns_linked_events(
    client: TestClient, db_session: Session
) -> None:
    """The brute-force alert's related-events endpoint returns its seven linked events."""
    alert_id = _alert_id(db_session, "ALERT-0001")

    response = client.get(f"/api/v1/alerts/{alert_id}/events")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 7
    assert len(body["items"]) == 7
    assert all(item["event_id"].startswith("evt-signal-brute-") for item in body["items"])


def test_get_alert_events_returns_empty_not_404_when_unlinked(
    client: TestClient, db_session: Session
) -> None:
    """The correlated chain alert has no directly linked events: 200 with an empty list."""
    alert_id = _alert_id(db_session, "ALERT-0006")

    response = client.get(f"/api/v1/alerts/{alert_id}/events")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_get_alert_events_not_found(client: TestClient) -> None:
    """Requesting related events for a nonexistent alert id returns 404."""
    response = client.get(f"/api/v1/alerts/{NONEXISTENT_ID}/events")

    assert response.status_code == 404


def test_update_alert_status_persists(client: TestClient, db_session: Session) -> None:
    """PATCHing an alert's status succeeds and the change is visible on a follow-up GET."""
    alert_id = _alert_id(db_session, "ALERT-1003")

    patch_response = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "closed"})

    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "closed"

    get_response = client.get(f"/api/v1/alerts/{alert_id}")
    assert get_response.json()["status"] == "closed"


def test_update_alert_status_invalid_value_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    """PATCHing an alert with an invalid status string returns 422."""
    alert_id = _alert_id(db_session, "ALERT-1003")

    response = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": "not_a_status"})

    assert response.status_code == 422


def test_update_alert_null_status_is_rejected(client: TestClient, db_session: Session) -> None:
    """PATCHing a non-nullable alert field to null returns 422."""
    alert_id = _alert_id(db_session, "ALERT-1003")

    response = client.patch(f"/api/v1/alerts/{alert_id}", json={"status": None})

    assert response.status_code == 422


def test_update_alert_not_found(client: TestClient) -> None:
    """PATCHing a nonexistent alert id returns 404."""
    response = client.patch(f"/api/v1/alerts/{NONEXISTENT_ID}", json={"status": "closed"})

    assert response.status_code == 404
