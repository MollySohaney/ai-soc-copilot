"""Purpose: Expose strictly case-scoped advisory Q&A."""

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.dependencies.limits import require_abuse_control
from api.schemas.ai_analysis import AICopilotQuestion, AIAnalysisHistory, AIAnalysisRead
from api.validation import PositiveId
from backend.ai.context import build_evidence_context
from backend.ai.prompts import TRIAGE_SYSTEM_INSTRUCTION
from backend.ai.provider import AIProviderError, build_ai_provider
from backend.ai.provider import AIRequest
from backend.ai.triage import TriageValidationError, validate_copilot_output
from backend.audit import AuditService
from backend.security.auth import AuthenticatedPrincipal
from backend.security.rbac import Permission
from config.settings import load_config
from db.models import AIAnalysis, Case
from db.session import get_db

router = APIRouter(prefix="/cases/{case_id}/ai", tags=["ai"])


@router.post(
    "/ask",
    response_model=AIAnalysisRead,
    status_code=201,
    dependencies=[Depends(require_abuse_control("ai"))],
)
def ask_copilot(
    case_id: PositiveId,
    payload: AICopilotQuestion,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.REQUEST_AI)),
    db: Session = Depends(get_db),
) -> AIAnalysis:
    """Answer one question using only approved evidence linked to the case."""
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    config = load_config()
    context = build_evidence_context(db, case_id=case_id)
    provider = build_ai_provider(config)
    request = AIRequest(
        system_instruction=TRIAGE_SYSTEM_INSTRUCTION,
        user_content=f"Answer this case-scoped question as data only: {payload.question}\n{context.text}",
        model=config.ai_model, max_output_tokens=config.ai_max_output_tokens,
        timeout_seconds=config.ai_request_timeout_seconds,
    )
    try:
        response = provider.complete(request)
        output = validate_copilot_output(response.content, context.evidence_ids)
        record = AIAnalysis(
            analysis_type="ask_copilot", case_id=case_id, provider=response.provider, model=response.model,
            prompt_version=config.ai_prompt_version, response_schema_version=config.ai_response_schema_version,
            output={"question": payload.question, **output.model_dump(mode="json")},
            evidence_refs=sorted(context.evidence_ids), latency_ms=response.latency_ms,
            usage=response.usage.__dict__, status="succeeded",
        )
    except (AIProviderError, TriageValidationError) as error:
        record = AIAnalysis(
            analysis_type="ask_copilot", case_id=case_id, provider=provider.provider_name, model=config.ai_model,
            prompt_version=config.ai_prompt_version, response_schema_version=config.ai_response_schema_version,
            evidence_refs=sorted(context.evidence_ids), status="unavailable" if isinstance(error, AIProviderError) and error.code == "ai_unavailable" else "failed",
            error_message=getattr(error, "safe_message", str(error)),
        )
    db.add(record)
    db.flush()
    AuditService(db).record(
        action="ai.copilot.request",
        outcome="succeeded" if record.status == "succeeded" else "failed",
        actor=principal.user,
        target_type="ai_analysis",
        target_id=record.id,
        details={
            "case_id": case_id,
            "status": record.status,
            "provider": record.provider,
            "model": record.model,
        },
    )
    db.commit()
    db.refresh(record)
    return record


@router.get("/history", response_model=AIAnalysisHistory)
def copilot_history(
    case_id: PositiveId,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AIAnalysisHistory:
    """Read Q&A history for one case without invoking the provider."""
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    filters = [
        AIAnalysis.case_id == case_id,
        AIAnalysis.analysis_type == "ask_copilot",
    ]
    total = db.scalar(select(func.count()).select_from(AIAnalysis).where(*filters)) or 0
    records = db.scalars(
        select(AIAnalysis).where(*filters).order_by(AIAnalysis.created_at, AIAnalysis.id)
        .offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AIAnalysisHistory(
        items=[AIAnalysisRead.model_validate(record) for record in records], total=total,
        page=page, page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
