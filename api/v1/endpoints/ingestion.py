"""Purpose: Expose telemetry ingestion control and status endpoints."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.dependencies.limits import require_abuse_control
from api.schemas.ingestion import (
    IngestionCheckpointRead,
    IngestionConnectionTestRequest,
    IngestionConnectionTestResponse,
    IngestionRunHistory,
    IngestionRunRead,
    IngestionStatusResponse,
    IngestionSyncRequest,
    IngestionSyncResponse,
)
from api.validation import ProviderName, validate_time_window
from backend.ingestion import (
    ElasticIngestionAdapter,
    FixtureIngestionAdapter,
    IngestionAdapter,
    IngestionAdapterError,
    IngestionAuthenticationError,
    IngestionConfigurationError,
    IngestionConnectionError,
    IngestionFetchRequest,
    IngestionOrchestrator,
    IngestionTimeoutError,
)
from backend.audit import AuditService
from backend.security.auth import AuthenticatedPrincipal
from backend.security.rbac import Permission
from config.settings import AppConfig, load_config
from db.models import IngestionCheckpoint, IngestionRun
from db.session import get_db

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post(
    "/{provider}/test",
    response_model=IngestionConnectionTestResponse,
    dependencies=[Depends(require_abuse_control("ingestion"))],
)
def test_ingestion_connection(
    provider: ProviderName,
    payload: IngestionConnectionTestRequest | None = None,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.OPERATE_INTEGRATIONS)
    ),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(load_config),
) -> IngestionConnectionTestResponse:
    """Test a telemetry provider connection without exposing secrets."""
    source_name = payload.source_name if payload else None
    try:
        adapter = _build_adapter(provider, config, source_name=source_name)
        health = adapter.test_connection()
    except Exception as error:  # noqa: BLE001
        AuditService(db).record(
            action="integration.test",
            outcome="failed",
            actor=principal.user,
            target_type="integration",
            target_id=provider.lower(),
            details={"source_name": source_name, "error_type": type(error).__name__},
        )
        db.commit()
        _raise_http_error(error)
    AuditService(db).record(
        action="integration.test",
        outcome="succeeded",
        actor=principal.user,
        target_type="integration",
        target_id=provider.lower(),
        details={"source_name": source_name, "ok": health.ok},
    )
    db.commit()
    return IngestionConnectionTestResponse.model_validate(health.model_dump())


@router.post(
    "/{provider}/sync",
    response_model=IngestionSyncResponse,
    dependencies=[Depends(require_abuse_control("ingestion"))],
)
def sync_ingestion(
    provider: ProviderName,
    payload: IngestionSyncRequest,
    principal: AuthenticatedPrincipal = Depends(
        require_permission(Permission.OPERATE_INTEGRATIONS)
    ),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(load_config),
) -> IngestionSyncResponse:
    """Run one bounded ingestion sync for a telemetry provider."""
    if payload.limit > config.max_ingestion_sync_limit:
        raise HTTPException(
            status_code=422,
            detail=f"limit must be less than or equal to {config.max_ingestion_sync_limit}",
        )
    validate_time_window(
        payload.start_time,
        payload.end_time,
        max_days=config.api_max_query_window_days,
    )
    adapter = _build_adapter(provider, config, source_name=payload.source_name)
    request = IngestionFetchRequest(
        start_time=payload.start_time,
        end_time=payload.end_time,
        limit=payload.limit,
    )
    try:
        def _record_run(run: IngestionRun) -> None:
            AuditService(db).record(
                action="integration.sync",
                outcome="failed" if run.status == "failed" else "succeeded",
                actor=principal.user,
                target_type="ingestion_run",
                target_id=run.id,
                details={
                    "provider": run.provider,
                    "source_name": run.source_name,
                    "status": run.status,
                    "dry_run": payload.dry_run,
                },
            )

        result = IngestionOrchestrator(
            db,
            adapter,
            retry_attempts=config.ingestion_retry_attempts,
            retry_backoff_seconds=config.ingestion_retry_backoff_seconds,
        ).run(request, dry_run=payload.dry_run, before_commit=_record_run)
    except Exception as error:  # noqa: BLE001
        _raise_http_error(error)

    return IngestionSyncResponse.model_validate(result.model_dump())


@router.get(
    "/status",
    response_model=IngestionStatusResponse,
    dependencies=[Depends(require_permission(Permission.OPERATE_INTEGRATIONS))],
)
def get_ingestion_status(db: Session = Depends(get_db)) -> IngestionStatusResponse:
    """Return latest ingestion run and current checkpoints."""
    latest_run = db.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc()).limit(1)
    ).first()
    checkpoints = db.scalars(
        select(IngestionCheckpoint).order_by(
            IngestionCheckpoint.updated_at.desc(), IngestionCheckpoint.id.desc()
        ).limit(100)
    ).all()
    return IngestionStatusResponse(
        latest_run=IngestionRunRead.model_validate(latest_run) if latest_run else None,
        checkpoints=[
            IngestionCheckpointRead.model_validate(checkpoint) for checkpoint in checkpoints
        ],
    )


@router.get(
    "/runs",
    response_model=IngestionRunHistory,
    dependencies=[Depends(require_permission(Permission.OPERATE_INTEGRATIONS))],
)
def list_ingestion_runs(
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> IngestionRunHistory:
    """List ingestion run history, sorted by newest first."""
    total = db.scalar(select(func.count()).select_from(IngestionRun)) or 0
    runs = db.scalars(
        select(IngestionRun)
        .order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    total_pages = math.ceil(total / page_size) if total else 0
    return IngestionRunHistory(
        items=[IngestionRunRead.model_validate(run) for run in runs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def _build_adapter(
    provider: str, config: AppConfig, *, source_name: str | None = None
) -> IngestionAdapter:
    normalized_provider = provider.lower()
    if normalized_provider == "fixture":
        return FixtureIngestionAdapter(source_name=source_name or "fixture-default")
    if normalized_provider == "elastic":
        elastic_config = (
            config.model_copy(update={"elastic_source_name": source_name})
            if source_name
            else config
        )
        try:
            return ElasticIngestionAdapter(elastic_config)
        except IngestionAdapterError as error:
            _raise_http_error(error)
    raise HTTPException(status_code=404, detail=f"Unsupported ingestion provider: {provider}")


def _raise_http_error(error: Exception) -> None:
    if isinstance(error, HTTPException):
        raise error
    if isinstance(error, IngestionConfigurationError):
        raise HTTPException(status_code=400, detail=str(error)) from error
    if isinstance(error, IngestionAuthenticationError):
        raise HTTPException(status_code=401, detail=str(error)) from error
    if isinstance(error, IngestionTimeoutError):
        raise HTTPException(status_code=504, detail=str(error)) from error
    if isinstance(error, IngestionConnectionError):
        raise HTTPException(status_code=502, detail=str(error)) from error
    if isinstance(error, IngestionAdapterError):
        raise HTTPException(status_code=502, detail=str(error)) from error
    raise HTTPException(status_code=500, detail="Ingestion sync failed.") from error
