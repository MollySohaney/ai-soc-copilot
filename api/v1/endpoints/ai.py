"""Purpose: Expose explicit, non-mutating advisory AI analysis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.schemas.ai_analysis import AIAnalysisHistory, AIAnalysisRead, AIAnalysisRequest
from backend.ai.context import build_evidence_context
from backend.ai.provider import AIProviderError, build_ai_provider
from backend.ai.prompts import build_triage_request
from backend.ai.triage import TriageValidationError, validate_triage_output
from backend.security.rbac import Permission
from config.settings import load_config
from db.models import AIAnalysis, Alert
from db.session import get_db

router = APIRouter(prefix="/alerts/{alert_id}/ai", tags=["ai"])


def _analysis_read(record: AIAnalysis) -> AIAnalysisRead:
    return AIAnalysisRead.model_validate(record)


@router.post(
    "/triage",
    response_model=AIAnalysisRead,
    status_code=201,
    dependencies=[Depends(require_permission(Permission.REQUEST_AI))],
)
def request_triage(alert_id: int, payload: AIAnalysisRequest, db: Session = Depends(get_db)) -> AIAnalysis:
    """Explicitly request one advisory triage attempt for an alert."""
    del payload
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    config = load_config()
    context = build_evidence_context(db, alert_id=alert_id)
    provider = build_ai_provider(config)
    try:
        response = provider.complete(build_triage_request(context, config))
        output = validate_triage_output(response.content, context.evidence_ids)
        record = AIAnalysis(
            analysis_type="triage", alert_id=alert_id, provider=response.provider,
            model=response.model, prompt_version=config.ai_prompt_version,
            response_schema_version=config.ai_response_schema_version,
            output=output.model_dump(mode="json"), evidence_refs=sorted(context.evidence_ids),
            latency_ms=response.latency_ms, usage=response.usage.__dict__, status="succeeded",
        )
    except (AIProviderError, TriageValidationError) as error:
        record = AIAnalysis(
            analysis_type="triage", alert_id=alert_id, provider=provider.provider_name,
            model=config.ai_model, prompt_version=config.ai_prompt_version,
            response_schema_version=config.ai_response_schema_version,
            evidence_refs=sorted(context.evidence_ids),
            status="unavailable" if isinstance(error, AIProviderError) and error.code == "ai_unavailable" else "failed",
            error_message=getattr(error, "safe_message", str(error)),
        )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/history", response_model=AIAnalysisHistory)
def list_triage_history(alert_id: int, db: Session = Depends(get_db)) -> AIAnalysisHistory:
    """Read prior analysis attempts without invoking an AI provider."""
    if db.get(Alert, alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    records = db.scalars(select(AIAnalysis).where(AIAnalysis.alert_id == alert_id).order_by(AIAnalysis.created_at, AIAnalysis.id)).all()
    return AIAnalysisHistory(items=[_analysis_read(record) for record in records], total=len(records))


@router.get("/analyses/{analysis_id}", response_model=AIAnalysisRead)
def get_analysis(alert_id: int, analysis_id: int, db: Session = Depends(get_db)) -> AIAnalysis:
    """Read one analysis only when it belongs to the requested alert."""
    record = db.scalar(select(AIAnalysis).where(AIAnalysis.id == analysis_id, AIAnalysis.alert_id == alert_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return record
