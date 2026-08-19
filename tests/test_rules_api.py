"""Purpose: Verify the /rules API endpoints against the seeded demo dataset."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db.models.detection_rule import DetectionRule

NONEXISTENT_ID = 99999
SEEDED_RULE_COUNT = 5


def _rule_id(db_session: Session, name: str) -> int:
    return db_session.query(DetectionRule).filter_by(name=name).one().id


def _valid_payload(**overrides: object) -> dict:
    payload = {
        "name": "New Test Rule",
        "description": "A rule created by a test.",
        "source": "custom",
        "language": "sigma",
        "query": "event_category:test",
        "severity": "medium",
        "risk_score": 50,
        "enabled": True,
        "mitre_tactic": "Discovery",
        "mitre_technique_id": "T1082",
        "mitre_technique_name": "System Information Discovery",
    }
    payload.update(overrides)
    return payload


def test_create_rule_valid_payload_succeeds(client: TestClient) -> None:
    """A valid rule payload is created and returned with a 201 status."""
    response = client.post("/api/v1/rules", json=_valid_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "New Test Rule"
    assert body["severity"] == "medium"
    assert "id" in body


def test_create_rule_invalid_language_is_rejected(client: TestClient) -> None:
    """A language outside the allowed set returns 422."""
    response = client.post("/api/v1/rules", json=_valid_payload(language="cobol"))

    assert response.status_code == 422


def test_create_rule_invalid_mitre_technique_id_format_is_rejected(
    client: TestClient,
) -> None:
    """A mitre_technique_id not matching T####[.###] returns 422."""
    response = client.post(
        "/api/v1/rules", json=_valid_payload(mitre_technique_id="X123")
    )

    assert response.status_code == 422


def test_create_rule_invalid_mitre_tactic_is_rejected(client: TestClient) -> None:
    """A mitre_tactic outside the 14 canonical tactics returns 422."""
    response = client.post(
        "/api/v1/rules", json=_valid_payload(mitre_tactic="Not A Real Tactic")
    )

    assert response.status_code == 422


def test_create_rule_risk_score_out_of_range_is_rejected(client: TestClient) -> None:
    """A risk_score above the allowed maximum of 100 returns 422."""
    response = client.post("/api/v1/rules", json=_valid_payload(risk_score=150))

    assert response.status_code == 422


def test_create_rule_duplicate_name_returns_409(client: TestClient) -> None:
    """Creating a rule whose name collides with a seeded rule returns 409."""
    response = client.post(
        "/api/v1/rules", json=_valid_payload(name="SSH Brute Force Detection")
    )

    assert response.status_code == 409


def test_list_rules_default_page_shape(client: TestClient) -> None:
    """The default listing returns every seeded rule on a single page."""
    response = client.get("/api/v1/rules")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == SEEDED_RULE_COUNT
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert body["total_pages"] == 1
    assert len(body["items"]) == SEEDED_RULE_COUNT


def test_list_rules_pagination(client: TestClient) -> None:
    """page_size=2 splits the seeded rules into disjoint, correctly-counted pages."""
    page1 = client.get("/api/v1/rules", params={"page": 1, "page_size": 2}).json()
    page2 = client.get("/api/v1/rules", params={"page": 2, "page_size": 2}).json()

    assert page1["total"] == SEEDED_RULE_COUNT
    assert page1["total_pages"] == 3
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2

    ids_page1 = {item["id"] for item in page1["items"]}
    ids_page2 = {item["id"] for item in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_get_rule_by_id(client: TestClient, db_session: Session) -> None:
    """Retrieving a rule by its id returns 200 with the matching record."""
    rule_id = _rule_id(db_session, "SSH Brute Force Detection")

    response = client.get(f"/api/v1/rules/{rule_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "SSH Brute Force Detection"


def test_get_rule_by_id_not_found(client: TestClient) -> None:
    """Retrieving a nonexistent rule id returns 404."""
    response = client.get(f"/api/v1/rules/{NONEXISTENT_ID}")

    assert response.status_code == 404


def test_patch_rule_partial_update_succeeds(
    client: TestClient, db_session: Session
) -> None:
    """PATCHing a subset of fields updates only those fields."""
    rule_id = _rule_id(db_session, "Unusual Outbound Network Connection Volume")

    response = client.patch(f"/api/v1/rules/{rule_id}", json={"enabled": False})

    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    # Untouched fields are preserved.
    assert body["name"] == "Unusual Outbound Network Connection Volume"


def test_patch_rule_invalid_data_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    """PATCHing with an invalid field value returns 422."""
    rule_id = _rule_id(db_session, "Unusual Outbound Network Connection Volume")

    response = client.patch(f"/api/v1/rules/{rule_id}", json={"risk_score": 999})

    assert response.status_code == 422


def test_patch_rule_not_found(client: TestClient) -> None:
    """PATCHing a nonexistent rule id returns 404."""
    response = client.patch(f"/api/v1/rules/{NONEXISTENT_ID}", json={"enabled": False})

    assert response.status_code == 404


def test_patch_rule_rename_collision_returns_409(
    client: TestClient, db_session: Session
) -> None:
    """Renaming a rule via PATCH to another existing rule's name returns 409."""
    rule_id = _rule_id(db_session, "Unusual Outbound Network Connection Volume")

    response = client.patch(
        f"/api/v1/rules/{rule_id}", json={"name": "SSH Brute Force Detection"}
    )

    assert response.status_code == 409
