"""Purpose: Provide provider-neutral telemetry ingestion primitives."""

from __future__ import annotations

from backend.ingestion.adapters import (
    ElasticIngestionAdapter,
    FixtureIngestionAdapter,
    IngestionAdapter,
)
from backend.ingestion.dto import (
    AdapterHealth,
    IngestionCheckpointState,
    IngestionFetchRequest,
    IngestionPage,
    IngestionRunResult,
    SourceRecord,
)
from backend.ingestion.errors import (
    IngestionAdapterError,
    IngestionAuthenticationError,
    IngestionConfigurationError,
    IngestionConnectionError,
    IngestionTimeoutError,
)
from backend.ingestion.normalizers import (
    NORMALIZATION_VERSION,
    EcsEventNormalizer,
    NormalizedEvent,
)
from backend.ingestion.orchestrator import IngestionOrchestrator

__all__ = [
    "AdapterHealth",
    "ElasticIngestionAdapter",
    "FixtureIngestionAdapter",
    "IngestionAdapter",
    "IngestionCheckpointState",
    "IngestionFetchRequest",
    "IngestionPage",
    "IngestionRunResult",
    "SourceRecord",
    "IngestionAdapterError",
    "IngestionAuthenticationError",
    "IngestionConfigurationError",
    "IngestionConnectionError",
    "IngestionTimeoutError",
    "EcsEventNormalizer",
    "NormalizedEvent",
    "NORMALIZATION_VERSION",
    "IngestionOrchestrator",
]
