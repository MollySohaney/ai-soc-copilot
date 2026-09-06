"""Purpose: Prove idempotency, readiness, and reliability boundaries."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.main import app
from backend.reliability import IdempotencyConflict, IdempotencyReplay, IdempotencyService
from config.settings import load_config
from db.models import IdempotencyRecord, User
from db.session import get_db


def test_health_and_readiness_are_safe(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/api/v1/health").json()["status"] == "ok"
    ready = anonymous_client.get("/api/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert "postgres" not in ready.text.lower()


def test_readiness_returns_generic_503_when_database_is_unavailable(
    anonymous_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.v1.endpoints.health.text",
        lambda _sql: (_ for _ in ()).throw(RuntimeError("database secret")),
    )
    response = anonymous_client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["error"]["message"] == "Service temporarily unavailable."
    assert "secret" not in response.text


def test_idempotency_replays_success_and_rejects_mismatch(db_session) -> None:  # noqa: ANN001
    actor = db_session.scalar(select(User).where(User.username == "test-analyst"))
    assert actor is not None
    service = IdempotencyService(db_session)
    first = service.begin(
        actor_user_id=actor.id, operation="case.create", key="same-key", payload={"title": "A"}
    )
    assert isinstance(first, IdempotencyRecord)
    service.complete(first, status_code=201, body={"id": 42})
    replay = service.begin(
        actor_user_id=actor.id, operation="case.create", key="same-key", payload={"title": "A"}
    )
    assert isinstance(replay, IdempotencyReplay)
    with pytest.raises(IdempotencyConflict, match="different request"):
        service.begin(
            actor_user_id=actor.id, operation="case.create", key="same-key", payload={"title": "B"}
        )


def test_case_create_idempotency_returns_one_canonical_case(client: TestClient, db_session) -> None:  # noqa: ANN001
    body = {"title": "Idempotent case", "priority": "high"}
    headers = {"Idempotency-Key": "case-key-1"}
    first = client.post("/api/v1/cases", json=body, headers=headers)
    second = client.post("/api/v1/cases", json=body, headers=headers)
    mismatch = client.post(
        "/api/v1/cases", json={"title": "Different"}, headers=headers
    )
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert mismatch.status_code == 409
    assert db_session.query(IdempotencyRecord).count() == 1


def test_ai_triage_idempotency_replays_without_second_provider_call(
    client: TestClient, db_session, monkeypatch: pytest.MonkeyPatch
) -> None:  # noqa: ANN001
    from backend.ai.provider import FakeAIProvider
    from db.models import Alert

    alert = db_session.scalar(select(Alert).where(Alert.external_id == "ALERT-0005"))
    assert alert is not None
    provider = FakeAIProvider(
        content='{"summary":"x","assessment":"y","confidence":0.5,'
        f'"evidence_refs":["alert-{alert.id}"]}}'
    )
    monkeypatch.setattr("api.v1.endpoints.ai.build_ai_provider", lambda _config: provider)
    headers = {"Idempotency-Key": "ai-key-1"}
    first = client.post(f"/api/v1/alerts/{alert.id}/ai/triage", json={}, headers=headers)
    second = client.post(f"/api/v1/alerts/{alert.id}/ai/triage", json={}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert provider.calls == 1
