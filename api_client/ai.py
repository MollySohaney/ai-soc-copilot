"""Purpose: Provide typed client functions for advisory AI analysis endpoints."""

from __future__ import annotations

import httpx

from api.schemas.ai_analysis import AIAnalysisHistory, AIAnalysisRead
from api_client.http import _request, get_default_client


def request_triage(alert_id: int, *, client: httpx.Client | None = None) -> AIAnalysisRead:
    """Explicitly request one alert triage attempt."""
    response = _request(client or get_default_client(), "POST", f"/alerts/{alert_id}/ai/triage", json={})
    return AIAnalysisRead.model_validate(response.json())


def get_triage_history(alert_id: int, *, client: httpx.Client | None = None) -> AIAnalysisHistory:
    """Read alert analysis history without triggering analysis."""
    response = _request(client or get_default_client(), "GET", f"/alerts/{alert_id}/ai/history")
    return AIAnalysisHistory.model_validate(response.json())


def draft_report(case_id: int, *, client: httpx.Client | None = None) -> AIAnalysisRead:
    """Explicitly request one case report draft."""
    response = _request(client or get_default_client(), "POST", f"/cases/{case_id}/ai/report")
    return AIAnalysisRead.model_validate(response.json())
