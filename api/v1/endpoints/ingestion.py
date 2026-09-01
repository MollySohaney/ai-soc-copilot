"""Purpose: Expose telemetry ingestion control and status endpoints."""

from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

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
from config.settings import AppConfig, load_config
from db.models import IngestionCheckpoint, IngestionRun
from db.session import get_db

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/{provider}/test", response_model=IngestionConnectionTestResponse)
def test_ingestion_connection(
    provider: str,
    payload: IngestionConnectionTestRequest | None = None,
    config: AppConfig = Depends(load_config),
) -> IngestionConnectionTestResponse:
    """Test a telemetry provider connection without exposing secrets."""
    adapter = _build_adapter(provider, config, source_name=payload.source_name if payload else None)
    health = adapter.test_connection()
    return IngestionConnectionTestResponse.model_validate(health.model_dump())


@router.post("/{provider}/sync", response_model=IngestionSyncResponse)
def sync_ingestion(
    provider: str,
    payload: IngestionSyncRequest,
    db: Session = Depends(get_db),
    config: AppConfig = Depends(load_config),
) -> IngestionSyncResponse:
    """Run one bounded ingestion sync for a telemetry provider."""
    adapter = _build_adapter(provider, config, source_name=payload.source_name)
    request = IngestionFetchRequest(
        start_time=payload.start_time,
        end_time=payload.end_time,
        limit=payload.limit,
    )
    try:
        result = IngestionOrchestrator(db, adapter).run(request, dry_run=payload.dry_run)
    except Exception as error:  # noqa: BLE001
        _raise_http_error(error)

    return IngestionSyncResponse.model_validate(result.model_dump())


@router.get("/status", response_model=IngestionStatusResponse)
def get_ingestion_status(db: Session = Depends(get_db)) -> IngestionStatusResponse:
    """Return latest ingestion run and current checkpoints."""
    latest_run = db.scalars(
        select(IngestionRun).order_by(IngestionRun.started_at.desc(), IngestionRun.id.desc()).limit(1)
    ).first()
    checkpoints = db.scalars(
        select(IngestionCheckpoint).order_by(
            IngestionCheckpoint.updated_at.desc(), IngestionCheckpoint.id.desc()
        )
    ).all()
    return IngestionStatusResponse(
        latest_run=IngestionRunRead.model_validate(latest_run) if latest_run else None,
        checkpoints=[
            IngestionCheckpointRead.model_validate(checkpoint) for checkpoint in checkpoints
        ],
    )


@router.get("/runs", response_model=IngestionRunHistory)
def list_ingestion_runs(
    page: int = Query(default=1, ge=1),
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
