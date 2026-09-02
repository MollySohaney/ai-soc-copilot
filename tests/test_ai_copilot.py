"""Purpose: Verify case-scoped advisory Q&A and append-only history."""

from backend.ai.provider import FakeAIProvider
from db.models import Case


def test_copilot_question_is_case_scoped_and_persisted(client, monkeypatch, db_session) -> None:  # noqa: ANN001
    case = db_session.query(Case).filter_by(case_number="CASE-2026-0001").one()
    provider = FakeAIProvider(content='{"answer":"The case has linked evidence.","assessment":"Review is warranted.","confidence":0.8,"evidence_refs":["case-%d"]}' % case.id)
    monkeypatch.setattr("api.v1.endpoints.copilot.build_ai_provider", lambda config: provider)

    response = client.post(f"/api/v1/cases/{case.id}/ai/ask", json={"question": "What happened?"})

    assert response.status_code == 201
    assert response.json()["output"]["question"] == "What happened?"
    assert provider.calls == 1
    assert client.get(f"/api/v1/cases/{case.id}/ai/history").json()["total"] == 1


def test_copilot_rejects_unknown_case(client) -> None:  # noqa: ANN001
    response = client.post("/api/v1/cases/999999/ai/ask", json={"question": "What happened?"})
    assert response.status_code == 404
