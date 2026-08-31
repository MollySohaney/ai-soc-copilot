"""Purpose: Define request/response DTOs for telemetry ingestion APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class IngestionConnectionTestRequest(BaseModel):
    """Represent an optional source-specific connection test request."""

    source_name: str | None = None


class IngestionConnectionTestResponse(BaseModel):
    """Represent a sanitized ingestion provider connection test result."""

    provider: str
    source_name: str
    ok: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class IngestionSyncRequest(BaseModel):
    """Represent a bounded manual ingestion sync request."""

    start_time: datetime
    end_time: datetime
    limit: int = Field(default=100, gt=0, le=1000)
    dry_run: bool = False
    source_name: str | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "IngestionSyncRequest":
        """Ensure manual sync requests are bounded by a forward-moving time window."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class IngestionSyncResponse(BaseModel):
    """Represent the outcome of a manual ingestion sync."""

    run_id: int
    provider: str
    source_name: str
    status: str
    dry_run: bool
    fetched_count: int
    normalized_count: int
    persisted_count: int
    duplicate_count: int
    failed_count: int
    warning_count: int
    checkpoint_advanced: bool
    errors: list[str] = Field(default_factory=list)


class IngestionRunRead(BaseModel):
    """Represent an ingestion run for status and history views."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    source_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    requested_start: datetime | None = None
    requested_end: datetime | None = None
    checkpoint_before: dict[str, Any] | None = None
    checkpoint_after: dict[str, Any] | None = None
    fetched_count: int
    normalized_count: int
    persisted_count: int
    duplicate_count: int
    failed_count: int
    warning_count: int
    error_message: str | None = None


class IngestionCheckpointRead(BaseModel):
    """Represent current restart state for a provider source."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    source_name: str
    checkpoint: dict[str, Any] | None = None
    updated_at: datetime
    last_run_id: int | None = None


class IngestionStatusResponse(BaseModel):
    """Represent current ingestion status."""

    latest_run: IngestionRunRead | None = None
    checkpoints: list[IngestionCheckpointRead] = Field(default_factory=list)


class IngestionRunHistory(BaseModel):
    """Represent a page of ingestion runs."""

    items: list[IngestionRunRead]
    total: int
    page: int
    page_size: int
    total_pages: int
