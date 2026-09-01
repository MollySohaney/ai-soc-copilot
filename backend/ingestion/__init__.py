"""Purpose: Provide provider-neutral telemetry ingestion primitives."""

from __future__ import annotations

from backend.ingestion.adapters import FixtureIngestionAdapter, IngestionAdapter
from backend.ingestion.dto import (
    AdapterHealth,
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionPage,
    SourceRecord,
)

__all__ = [
    "AdapterHealth",
    "FixtureIngestionAdapter",
    "IngestionAdapter",
    "IngestionCheckpointState",
    "IngestionFetchRequest",
    "IngestionPage",
    "SourceRecord",
]
