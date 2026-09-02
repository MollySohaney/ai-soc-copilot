"""Purpose: Verify report drafts remain case-scoped and evidence-grounded."""

from backend.ai.provider import FakeAIProvider
from db.models import Case


def test_report_draft_persists_provenance_and_citations(client, monkeypatch, db_session) -> None:  # noqa: ANN001
    case = db_session.query(Case).filter_by(case_number="CASE-2026-0001").one()
    response_body = '{"executive_summary":"Confirmed activity.","technical_timeline":[],"indicators":[],"mitre":[],"actions_recorded":[],"recommendations":["Review access controls."],"evidence_refs":["case-%d"]}' % case.id
    monkeypatch.setattr("api.v1.endpoints.reports.build_ai_provider", lambda config: FakeAIProvider(response_body))

    response = client.post(f"/api/v1/cases/{case.id}/ai/report")

    assert response.status_code == 201
    assert response.json()["analysis_type"] == "report_draft"
    assert response.json()["output"]["actions_recorded"] == []
