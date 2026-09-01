"""Purpose: Define the provider-neutral ingestion adapter protocol."""

from __future__ import annotations

from typing import Protocol

from backend.ingestion.dto import AdapterHealth, IngestionFetchRequest, IngestionPage


class IngestionAdapter(Protocol):
    """Represent a telemetry source that can provide bounded, checkpointed records."""

    @property
    def provider(self) -> str:
        """Return the provider identifier, such as elastic or fixture."""

    @property
    def source_name(self) -> str:
        """Return the configured source name within the provider."""

    def test_connection(self) -> AdapterHealth:
        """Check whether the source is reachable without exposing credentials."""

    def fetch_records(self, request: IngestionFetchRequest) -> IngestionPage:
        """Fetch one deterministic page of source records for the requested bounds."""
