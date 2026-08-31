"""Purpose: Provide typed client functions for telemetry ingestion endpoints."""

from __future__ import annotations

from datetime import datetime

import httpx

from api.schemas.ingestion import (
    IngestionConnectionTestResponse,
    IngestionRunHistory,
    IngestionStatusResponse,
    IngestionSyncResponse,
)
from api_client.http import _request, clean_params, get_default_client


def test_connection(
    provider: str,
    *,
    source_name: str | None = None,
    client: httpx.Client | None = None,
) -> IngestionConnectionTestResponse:
    """Test an ingestion provider connection without exposing secrets."""
    response = _request(
        client or get_default_client(),
        "POST",
        f"/ingestion/{provider}/test",
        json=clean_params(source_name=source_name),
    )
    return IngestionConnectionTestResponse.model_validate(response.json())


def sync_provider(
    provider: str,
    *,
    start_time: datetime,
    end_time: datetime,
    limit: int = 100,
    dry_run: bool = False,
    source_name: str | None = None,
    client: httpx.Client | None = None,
) -> IngestionSyncResponse:
    """Run one bounded ingestion sync for a provider."""
    payload = clean_params(
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        limit=limit,
        dry_run=dry_run,
        source_name=source_name,
    )
    response = _request(
        client or get_default_client(),
        "POST",
        f"/ingestion/{provider}/sync",
        json=payload,
    )
    return IngestionSyncResponse.model_validate(response.json())


def get_status(*, client: httpx.Client | None = None) -> IngestionStatusResponse:
    """Return current ingestion status."""
    response = _request(client or get_default_client(), "GET", "/ingestion/status")
    return IngestionStatusResponse.model_validate(response.json())


def list_runs(
    *,
    page: int = 1,
    page_size: int = 20,
    client: httpx.Client | None = None,
) -> IngestionRunHistory:
    """List ingestion run history."""
    params = clean_params(page=page, page_size=page_size)
    response = _request(client or get_default_client(), "GET", "/ingestion/runs", params=params)
    return IngestionRunHistory.model_validate(response.json())
