"""Purpose: Expose explicit, non-mutating advisory AI analysis endpoints."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from fastapi import Query
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.dependencies.limits import require_abuse_control
from api.schemas.ai_analysis import AIAnalysisHistory, AIAnalysisRead, AIAnalysisRequest
from api.validation import PositiveId
from backend.ai.context import build_evidence_context
from backend.ai.provider import AIProviderError, build_ai_provider
from backend.ai.prompts import build_triage_request
from backend.ai.triage import TriageValidationError, validate_triage_output
from backend.audit import AuditService
from backend.reliability import IdempotencyConflict, IdempotencyReplay, IdempotencyService
from backend.security.auth import AuthenticatedPrincipal
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
    dependencies=[Depends(require_abuse_control("ai"))],
)
def request_triage(
    alert_id: PositiveId,
    payload: AIAnalysisRequest,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.REQUEST_AI)),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> AIAnalysis:
    """Explicitly request one advisory triage attempt for an alert."""
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    idem = IdempotencyService(db)
    reservation = None
    if idempotency_key is not None:
        try:
            reservation = idem.begin(
                actor_user_id=principal.user.id,
                operation="ai.triage.request",
                key=idempotency_key,
                payload={"alert_id": alert_id, **payload.model_dump(mode="json")},
            )
        except IdempotencyConflict as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if isinstance(reservation, IdempotencyReplay):
            return JSONResponse(status_code=reservation.status_code, content=reservation.body)  # type: ignore[return-value]
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
    db.flush()
    AuditService(db).record(
        action="ai.triage.request",
        outcome="succeeded" if record.status == "succeeded" else "failed",
        actor=principal.user,
        target_type="ai_analysis",
        target_id=record.id,
        details={
            "alert_id": alert_id,
            "status": record.status,
            "provider": record.provider,
            "model": record.model,
        },
    )
    db.commit()
    db.refresh(record)
    if reservation is not None:
        idem.complete(reservation, status_code=201, body=AIAnalysisRead.model_validate(record).model_dump(mode="json"))
    return record


@router.get("/history", response_model=AIAnalysisHistory)
def list_triage_history(
    alert_id: PositiveId,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AIAnalysisHistory:
    """Read prior analysis attempts without invoking an AI provider."""
    if db.get(Alert, alert_id) is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    filters = [AIAnalysis.alert_id == alert_id]
    total = db.scalar(select(func.count()).select_from(AIAnalysis).where(*filters)) or 0
    records = db.scalars(
        select(AIAnalysis).where(*filters).order_by(AIAnalysis.created_at, AIAnalysis.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AIAnalysisHistory(
        items=[_analysis_read(record) for record in records], total=total,
        page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


@router.get("/analyses/{analysis_id}", response_model=AIAnalysisRead)
def get_analysis(
    alert_id: PositiveId,
    analysis_id: PositiveId,
    db: Session = Depends(get_db),
) -> AIAnalysis:
    """Read one analysis only when it belongs to the requested alert."""
    record = db.scalar(select(AIAnalysis).where(AIAnalysis.id == analysis_id, AIAnalysis.alert_id == alert_id))
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return record
