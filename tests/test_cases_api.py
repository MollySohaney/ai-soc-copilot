"""Purpose: Verify the /cases API endpoints against the seeded demo dataset."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models.alert import Alert
from db.models.case import Case
from db.models.case_alert import CaseAlert

NONEXISTENT_ID = 99999
SEEDED_CASE_COUNT = 3


def _case_id(db_session: Session, case_number: str) -> int:
    return db_session.query(Case).filter_by(case_number=case_number).one().id


def _alert_id(db_session: Session, external_id: str) -> int:
    return db_session.query(Alert).filter_by(external_id=external_id).one().id


def _case_alert_count(db_session: Session, case_id: int) -> int:
    return db_session.query(CaseAlert).filter_by(case_id=case_id).count()


def _case_count(db_session: Session) -> int:
    return db_session.query(Case).count()


# --- Listing / pagination / filters ---------------------------------------


def test_list_cases_default_page_shape(client: TestClient) -> None:
    """The default listing returns every seeded case on a single page."""
    response = client.get("/api/v1/cases")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == SEEDED_CASE_COUNT
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1
    assert len(body["items"]) == SEEDED_CASE_COUNT


def test_list_cases_pagination_returns_disjoint_stable_slices(client: TestClient) -> None:
    """page=2&page_size=1 returns a different, stably-ordered slice than page 1."""
    page1 = client.get("/api/v1/cases", params={"page": 1, "page_size": 1}).json()
    page2 = client.get("/api/v1/cases", params={"page": 2, "page_size": 1}).json()

    assert page1["total"] == SEEDED_CASE_COUNT
    assert page1["total_pages"] == SEEDED_CASE_COUNT
    assert len(page1["items"]) == 1
    assert len(page2["items"]) == 1

    ids_page1 = {item["id"] for item in page1["items"]}
    ids_page2 = {item["id"] for item in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)

    # Re-querying page 1 returns the exact same ordering (stable sort).
    page1_again = client.get("/api/v1/cases", params={"page": 1, "page_size": 1}).json()
    assert [item["id"] for item in page1["items"]] == [item["id"] for item in page1_again["items"]]


def test_list_cases_oversized_page_size_is_rejected(client: TestClient) -> None:
    """A page_size above the allowed maximum of 100 is rejected with 422."""
    response = client.get("/api/v1/cases", params={"page_size": 101})

    assert response.status_code == 422


def test_filter_cases_by_status(client: TestClient) -> None:
    """Filtering by status=resolved returns only the seeded resolved case."""
    response = client.get("/api/v1/cases", params={"status": "resolved"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["case_number"] == "CASE-2026-0002"
    assert all(item["status"] == "resolved" for item in body["items"])


def test_filter_cases_by_priority(client: TestClient) -> None:
    """Filtering by priority=critical returns only the seeded critical case."""
    response = client.get("/api/v1/cases", params={"priority": "critical"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["case_number"] == "CASE-2026-0001"
    assert all(item["priority"] == "critical" for item in body["items"])


def test_filter_cases_by_assignee(client: TestClient) -> None:
    """Filtering by assignee matches the seeded case assigned to that analyst, case-insensitively."""
    response = client.get("/api/v1/cases", params={"assignee": "Analyst.Rivera"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["case_number"] == "CASE-2026-0001"
    assert all(item["assignee"] == "analyst.rivera" for item in body["items"])


# --- Case creation -----------------------------------------------------


def test_create_case_without_alerts(client: TestClient) -> None:
    """Creating a case with no alert_ids succeeds and returns an empty alerts list."""
    response = client.post(
        "/api/v1/cases",
        json={"title": "New investigation", "priority": "high"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "New investigation"
    assert body["priority"] == "high"
    assert body["alerts"] == []


def test_create_case_generates_sequential_case_number(client: TestClient) -> None:
    """Two cases created in the current year get unique, incrementing CASE-{year}-NNNN numbers."""
    first = client.post("/api/v1/cases", json={"title": "Case A"}).json()
    second = client.post("/api/v1/cases", json={"title": "Case B"}).json()

    assert first["case_number"].startswith("CASE-")
    parts = first["case_number"].split("-")
    assert len(parts) == 3
    assert parts[1].isdigit()
    assert parts[2].isdigit()

    assert first["case_number"] != second["case_number"]
    first_seq = int(first["case_number"].rsplit("-", 1)[1])
    second_seq = int(second["case_number"].rsplit("-", 1)[1])
    assert second_seq == first_seq + 1


def test_create_case_with_alert_ids_links_alerts(
    client: TestClient, db_session: Session
) -> None:
    """Creating a case with alert_ids links those alerts and records a case_created activity."""
    filler_3_id = _alert_id(db_session, "ALERT-1003")
    filler_4_id = _alert_id(db_session, "ALERT-1004")

    response = client.post(
        "/api/v1/cases",
        json={"title": "Linked case", "alert_ids": [filler_3_id, filler_4_id]},
    )

    assert response.status_code == 201
    body = response.json()
    linked_ids = {alert["id"] for alert in body["alerts"]}
    assert linked_ids == {filler_3_id, filler_4_id}

    activity_types = [activity["activity_type"] for activity in body["activities"]]
    assert activity_types == ["case_created"]


def test_create_case_with_missing_alert_id_returns_404_and_creates_nothing(
    client: TestClient, db_session: Session
) -> None:
    """Creating a case referencing a nonexistent alert id fails with 404 and no case is created."""
    before_count = _case_count(db_session)

    response = client.post(
        "/api/v1/cases",
        json={"title": "Should not exist", "alert_ids": [NONEXISTENT_ID]},
    )

    assert response.status_code == 404
    assert _case_count(db_session) == before_count


# --- Case updates --------------------------------------------------------


def test_update_case_status_appends_activity(client: TestClient, db_session: Session) -> None:
    """Changing a case's status updates it and appends a status_change activity."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    response = client.patch(f"/api/v1/cases/{case_id}", json={"status": "in_progress"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "in_progress"
    status_change_activities = [
        a for a in body["activities"] if a["activity_type"] == "status_change"
    ]
    assert len(status_change_activities) == 1


def test_update_case_status_to_closed_sets_closed_at(
    client: TestClient, db_session: Session
) -> None:
    """Transitioning a case's status to closed sets closed_at."""
    case_id = _case_id(db_session, "CASE-2026-0003")
    assert client.get(f"/api/v1/cases/{case_id}").json()["closed_at"] is None

    response = client.patch(f"/api/v1/cases/{case_id}", json={"status": "closed"})

    assert response.status_code == 200
    assert response.json()["closed_at"] is not None


def test_update_case_status_out_of_closed_clears_closed_at(
    client: TestClient, db_session: Session
) -> None:
    """Transitioning a case's status out of closed clears closed_at."""
    case_id = _case_id(db_session, "CASE-2026-0003")
    closed = client.patch(f"/api/v1/cases/{case_id}", json={"status": "closed"})
    assert closed.json()["closed_at"] is not None

    response = client.patch(f"/api/v1/cases/{case_id}", json={"status": "in_progress"})

    assert response.status_code == 200
    assert response.json()["closed_at"] is None


def test_update_case_priority_appends_activity(client: TestClient, db_session: Session) -> None:
    """Changing a case's priority updates it and appends a priority_change activity."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    response = client.patch(f"/api/v1/cases/{case_id}", json={"priority": "high"})

    assert response.status_code == 200
    body = response.json()
    assert body["priority"] == "high"
    priority_change_activities = [
        a for a in body["activities"] if a["activity_type"] == "priority_change"
    ]
    assert len(priority_change_activities) == 1


def test_update_case_invalid_status_returns_422(client: TestClient, db_session: Session) -> None:
    """PATCHing a case with an invalid status string returns 422."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    response = client.patch(f"/api/v1/cases/{case_id}", json={"status": "not_a_status"})

    assert response.status_code == 422


def test_update_case_invalid_priority_returns_422(
    client: TestClient, db_session: Session
) -> None:
    """PATCHing a case with an invalid priority string returns 422."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    response = client.patch(f"/api/v1/cases/{case_id}", json={"priority": "not_a_priority"})

    assert response.status_code == 422


def test_update_case_null_title_is_rejected(client: TestClient, db_session: Session) -> None:
    """PATCHing a non-nullable case field to null returns 422."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    response = client.patch(f"/api/v1/cases/{case_id}", json={"title": None})

    assert response.status_code == 422


def test_update_case_not_found(client: TestClient) -> None:
    """PATCHing a nonexistent case id returns 404."""
    response = client.patch(f"/api/v1/cases/{NONEXISTENT_ID}", json={"status": "closed"})

    assert response.status_code == 404


# --- Alert linking / unlinking -------------------------------------------


def test_add_alert_to_case_succeeds(client: TestClient, db_session: Session) -> None:
    """Adding an unlinked alert to a case succeeds, appears in alerts, and logs an activity."""
    case_id = _case_id(db_session, "CASE-2026-0003")
    filler_6_id = _alert_id(db_session, "ALERT-1006")

    response = client.post(
        f"/api/v1/cases/{case_id}/alerts", json={"alert_ids": [filler_6_id]}
    )

    assert response.status_code == 200
    body = response.json()
    assert filler_6_id in {alert["id"] for alert in body["alerts"]}
    assert any(a["activity_type"] == "alerts_added" for a in body["activities"])


def test_add_duplicate_alert_is_a_no_op(client: TestClient, db_session: Session) -> None:
    """Re-adding an alert already linked to a case doesn't duplicate the link or log an activity."""
    case_id = _case_id(db_session, "CASE-2026-0001")
    brute_force_id = _alert_id(db_session, "ALERT-0001")

    before_link_count = _case_alert_count(db_session, case_id)
    before_activity_count = len(client.get(f"/api/v1/cases/{case_id}").json()["activities"])

    response = client.post(
        f"/api/v1/cases/{case_id}/alerts", json={"alert_ids": [brute_force_id]}
    )

    assert response.status_code == 200
    assert _case_alert_count(db_session, case_id) == before_link_count
    after_activity_count = len(response.json()["activities"])
    assert after_activity_count == before_activity_count


def test_add_alert_to_nonexistent_case_returns_404(
    client: TestClient, db_session: Session
) -> None:
    """Adding an alert to a nonexistent case returns 404."""
    filler_6_id = _alert_id(db_session, "ALERT-1006")

    response = client.post(
        f"/api/v1/cases/{NONEXISTENT_ID}/alerts", json={"alert_ids": [filler_6_id]}
    )

    assert response.status_code == 404


def test_add_missing_alert_to_case_returns_404(client: TestClient, db_session: Session) -> None:
    """Adding a nonexistent alert id to a case returns 404."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    response = client.post(
        f"/api/v1/cases/{case_id}/alerts", json={"alert_ids": [NONEXISTENT_ID]}
    )

    assert response.status_code == 404


def test_remove_alert_from_case_succeeds(client: TestClient, db_session: Session) -> None:
    """Removing a linked alert succeeds, disappears from alerts, and logs an activity."""
    case_id = _case_id(db_session, "CASE-2026-0001")
    brute_force_id = _alert_id(db_session, "ALERT-0001")

    response = client.delete(f"/api/v1/cases/{case_id}/alerts/{brute_force_id}")

    assert response.status_code == 200
    body = response.json()
    assert brute_force_id not in {alert["id"] for alert in body["alerts"]}
    assert any(a["activity_type"] == "alert_removed" for a in body["activities"])


def test_remove_alert_not_linked_to_case_returns_404(
    client: TestClient, db_session: Session
) -> None:
    """Removing an alert that isn't linked to the given case returns 404."""
    case_id = _case_id(db_session, "CASE-2026-0003")
    unlinked_alert_id = _alert_id(db_session, "ALERT-1007")

    response = client.delete(f"/api/v1/cases/{case_id}/alerts/{unlinked_alert_id}")

    assert response.status_code == 404


def test_remove_alert_from_nonexistent_case_returns_404(
    client: TestClient, db_session: Session
) -> None:
    """Removing an alert from a nonexistent case returns 404."""
    response = client.delete(f"/api/v1/cases/{NONEXISTENT_ID}/alerts/{NONEXISTENT_ID}")

    assert response.status_code == 404


# --- Activities ------------------------------------------------------------


def test_add_analyst_note_appears_via_list(client: TestClient, db_session: Session) -> None:
    """Posting an analyst note to a case's activity log succeeds and shows up on a follow-up GET."""
    case_id = _case_id(db_session, "CASE-2026-0003")

    post_response = client.post(
        f"/api/v1/cases/{case_id}/activities",
        json={"activity_type": "note", "message": "Confirmed benign.", "author": "analyst.lee"},
    )

    assert post_response.status_code == 201
    posted = post_response.json()
    assert posted["message"] == "Confirmed benign."
    assert posted["author"] == "analyst.lee"

    list_response = client.get(f"/api/v1/cases/{case_id}/activities")
    assert list_response.status_code == 200
    messages = [item["message"] for item in list_response.json()["items"]]
    assert "Confirmed benign." in messages


def test_case_activities_ordered_chronologically(
    client: TestClient, db_session: Session
) -> None:
    """The chain case's activity timeline is returned in ascending created_at order."""
    case_id = _case_id(db_session, "CASE-2026-0001")

    response = client.get(f"/api/v1/cases/{case_id}/activities")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 5
    created_ats = [item["created_at"] for item in body["items"]]
    assert created_ats == sorted(created_ats)
    assert [item["activity_type"] for item in body["items"]] == [
        "triage",
        "note",
        "note",
        "note",
        "status_change",
    ]


def test_list_activities_for_nonexistent_case_returns_404(client: TestClient) -> None:
    """Listing activities for a nonexistent case returns 404."""
    response = client.get(f"/api/v1/cases/{NONEXISTENT_ID}/activities")

    assert response.status_code == 404


def test_create_activity_for_nonexistent_case_returns_404(client: TestClient) -> None:
    """Posting an activity to a nonexistent case returns 404."""
    response = client.post(
        f"/api/v1/cases/{NONEXISTENT_ID}/activities",
        json={"activity_type": "note", "message": "irrelevant"},
    )

    assert response.status_code == 404


# --- Basic get/not-found coverage ------------------------------------------


def test_get_case_returns_full_seeded_chain(client: TestClient, db_session: Session) -> None:
    """Fetching the chain case returns its 6 linked alerts and 5-entry activity timeline."""
    case_id = _case_id(db_session, "CASE-2026-0001")

    response = client.get(f"/api/v1/cases/{case_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["case_number"] == "CASE-2026-0001"
    assert body["status"] == "in_progress"
    assert body["priority"] == "critical"
    assert len(body["alerts"]) == 6
    assert len(body["activities"]) == 5


def test_get_case_not_found(client: TestClient) -> None:
    """Fetching a nonexistent case id returns 404."""
    response = client.get(f"/api/v1/cases/{NONEXISTENT_ID}")

    assert response.status_code == 404
