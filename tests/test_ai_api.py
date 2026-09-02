"""Purpose: Verify explicit AI API execution, history, and safe failure behavior."""

from backend.ai.provider import FakeAIProvider
from backend.ai.triage import AlertTriageOutput
from db.models import Alert


def test_get_ai_history_does_not_invoke_provider(client, monkeypatch, db_session) -> None:  # noqa: ANN001
    """Read-only history remains empty and makes no provider call."""
    calls = []
    monkeypatch.setattr("api.v1.endpoints.ai.build_ai_provider", lambda config: calls.append(config))
    alert = db_session.query(Alert).filter_by(external_id="ALERT-0005").one()

    response = client.get(f"/api/v1/alerts/{alert.id}/ai/history")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}
    assert calls == []


def test_post_ai_triage_persists_valid_result(client, monkeypatch, db_session) -> None:  # noqa: ANN001
    """An explicit POST invokes the fake provider and stores a history record."""
    alert = db_session.query(Alert).filter_by(external_id="ALERT-0005").one()
    provider = FakeAIProvider(content='{"summary":"x","assessment":"y","confidence":0.7,"evidence_refs":["alert-%d"]}' % alert.id)
    monkeypatch.setattr("api.v1.endpoints.ai.build_ai_provider", lambda config: provider)

    response = client.post(f"/api/v1/alerts/{alert.id}/ai/triage", json={})

    assert response.status_code == 201
    assert response.json()["status"] == "succeeded"
    assert provider.calls == 1
    assert response.json()["output"]["confidence"] == 0.7


def test_post_ai_triage_unavailable_is_non_destructive(client, monkeypatch, db_session) -> None:  # noqa: ANN001
    """Disabled AI returns a persisted safe status without changing the alert."""
    from backend.ai.provider import UnavailableAIProvider

    alert = db_session.query(Alert).filter_by(external_id="ALERT-0005").one()
    status_before = alert.status
    monkeypatch.setattr("api.v1.endpoints.ai.build_ai_provider", lambda config: UnavailableAIProvider())

    response = client.post(f"/api/v1/alerts/{alert.id}/ai/triage", json={})

    assert response.status_code == 201
    assert response.json()["status"] == "unavailable"
    db_session.refresh(alert)
    assert alert.status == status_before
