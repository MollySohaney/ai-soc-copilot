"""Purpose: Expose evidence-grounded, non-executing case report drafts."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.schemas.ai_analysis import AIAnalysisRead
from api.schemas.report import ReportDraftOutput
from backend.ai.context import build_evidence_context
from backend.ai.prompts import TRIAGE_SYSTEM_INSTRUCTION
from backend.ai.provider import AIProviderError, AIRequest, build_ai_provider
from backend.ai.triage import TriageValidationError
from backend.audit import AuditService
from backend.security.auth import AuthenticatedPrincipal
from backend.security.rbac import Permission
from config.settings import load_config
from db.models import AIAnalysis, Case
from db.session import get_db

router = APIRouter(prefix="/cases/{case_id}/ai", tags=["ai"])


@router.post(
    "/report",
    response_model=AIAnalysisRead,
    status_code=201,
)
def draft_report(
    case_id: int,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.REQUEST_AI)),
    db: Session = Depends(get_db),
) -> AIAnalysis:
    """Create one reviewable report draft from the active case evidence."""
    if db.get(Case, case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    config = load_config()
    context = build_evidence_context(db, case_id=case_id)
    provider = build_ai_provider(config)
    request = AIRequest(
        system_instruction=TRIAGE_SYSTEM_INSTRUCTION + "\nActions taken must contain only actions explicitly recorded in evidence.",
        user_content=f"Draft a report from confirmed case evidence only. Recommendations are advisory.\n{context.text}",
        model=config.ai_model, max_output_tokens=config.ai_max_output_tokens,
        timeout_seconds=config.ai_request_timeout_seconds,
    )
    try:
        response = provider.complete(request)
        output = ReportDraftOutput.model_validate(__import__("json").loads(response.content))
        unsupported = set(output.evidence_refs) - set(context.evidence_ids)
        if unsupported:
            raise TriageValidationError("Report cited evidence outside the supplied context.")
        record = AIAnalysis(
            analysis_type="report_draft", case_id=case_id, provider=response.provider, model=response.model,
            prompt_version=config.ai_prompt_version, response_schema_version=config.ai_response_schema_version,
            output=output.model_dump(mode="json"), evidence_refs=sorted(context.evidence_ids),
            latency_ms=response.latency_ms, usage=response.usage.__dict__, status="succeeded",
        )
    except (AIProviderError, TriageValidationError, ValueError) as error:
        record = AIAnalysis(
            analysis_type="report_draft", case_id=case_id, provider=provider.provider_name, model=config.ai_model,
            prompt_version=config.ai_prompt_version, response_schema_version=config.ai_response_schema_version,
            evidence_refs=sorted(context.evidence_ids), status="unavailable" if isinstance(error, AIProviderError) and error.code == "ai_unavailable" else "failed",
            error_message=getattr(error, "safe_message", "Report draft could not be validated."),
        )
    db.add(record)
    db.flush()
    AuditService(db).record(
        action="ai.report.request",
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
