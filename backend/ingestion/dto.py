"""Purpose: Define provider-neutral telemetry ingestion DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class AdapterHealth(BaseModel):
    """Represent a sanitized adapter connection check result."""

    provider: str
    source_name: str
    ok: bool
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class IngestionCheckpointState(BaseModel):
    """Represent opaque restart state returned by an ingestion adapter."""

    provider: str
    source_name: str
    values: dict[str, Any] = Field(default_factory=dict)


class SourceRecord(BaseModel):
    """Represent one provider-neutral telemetry record before normalization."""

    provider: str
    source_name: str
    record_id: str
    timestamp: datetime
    payload: dict[str, Any]
    source_index: str | None = None
    cursor: list[Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        """Return a stable provider-neutral deduplication key."""
        index = self.source_index or "-"
        return f"{self.provider}:{self.source_name}:{index}:{self.record_id}"


class IngestionFetchRequest(BaseModel):
    """Represent one bounded fetch request issued to an ingestion adapter."""

    start_time: datetime
    end_time: datetime
    limit: int = Field(default=100, gt=0, le=1000)
    checkpoint: IngestionCheckpointState | None = None

    @model_validator(mode="after")
    def validate_time_window(self) -> "IngestionFetchRequest":
        """Ensure fetch requests are bounded by a forward-moving time window."""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time.")
        return self


class IngestionPage(BaseModel):
    """Represent one page of fetched source records and restart state."""

    records: list[SourceRecord]
    next_checkpoint: IngestionCheckpointState | None = None
    has_more: bool = False

    @field_validator("records")
    @classmethod
    def validate_deterministic_order(cls, value: list[SourceRecord]) -> list[SourceRecord]:
        """Ensure adapter pages are stable for checkpointed ingestion."""
        sorted_records = sorted(value, key=lambda record: (record.timestamp, record.record_id))
        if value != sorted_records:
            raise ValueError("records must be sorted by timestamp and record_id.")
        return value
