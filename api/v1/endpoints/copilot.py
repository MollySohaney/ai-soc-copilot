"""Purpose: Expose strictly case-scoped advisory Q&A."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.schemas.ai_analysis import AICopilotQuestion, AIAnalysisHistory, AIAnalysisRead
from backend.ai.context import build_evidence_context
from backend.ai.prompts import TRIAGE_SYSTEM_INSTRUCTION
from backend.ai.provider import AIProviderError, build_ai_provider
from backend.ai.provider import AIRequest
from backend.ai.triage import TriageValidationError, validate_copilot_output
from backend.security.rbac import Permission
from config.settings import load_config
from db.models import AIAnalysis, Case
from db.session import get_db

router = APIRouter(prefix="/cases/{case_id}/ai", tags=["ai"])


@router.post(
    "/ask",
    response_model=AIAnalysisRead,
    status_code=201,
    dependencies=[Depends(require_permission(Permission.REQUEST_AI))],
)
def ask_copilot(case_id: int, payload: AICopilotQuestion, db: Session = Depends(get_db)) -> AIAnalysis:
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
    db.commit()
    db.refresh(record)
    return record


@router.get("/history", response_model=AIAnalysisHistory)
def copilot_history(case_id: int, db: Session = Depends(get_db)) -> AIAnalysisHistory:
    """Read Q&A history for one case without invoking the provider."""
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    records = db.scalars(select(AIAnalysis).where(AIAnalysis.case_id == case_id, AIAnalysis.analysis_type == "ask_copilot").order_by(AIAnalysis.created_at, AIAnalysis.id)).all()
    return AIAnalysisHistory(items=[AIAnalysisRead.model_validate(record) for record in records], total=len(records))
