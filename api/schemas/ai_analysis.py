"""Purpose: Define safe API DTOs for advisory AI analysis."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AIAnalysisRequest(BaseModel):
    """Represent an explicit analysis request with no credentials or commands."""

    model_config = ConfigDict(extra="forbid")


class AIAnalysisRead(BaseModel):
    """Represent persisted analysis status and non-secret operational metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_type: str
    alert_id: int | None
    case_id: int | None
    provider: str
    model: str
    prompt_version: str
    response_schema_version: str
    output: dict[str, Any] | None
    evidence_refs: list[Any] | None
    latency_ms: int | None
    usage: dict[str, Any] | None
    rate_limit_remaining: int | None
    estimated_cost_usd: float | None
    status: str
    error_message: str | None
    created_at: datetime


class AIAnalysisHistory(BaseModel):
    """Represent append-only analysis history for one alert."""

    items: list[AIAnalysisRead]
    total: int
