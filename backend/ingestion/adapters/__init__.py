"""Purpose: Expose ingestion adapter implementations."""

from __future__ import annotations

from backend.ingestion.adapters.base import IngestionAdapter
from backend.ingestion.adapters.fixture import FixtureIngestionAdapter

__all__ = ["FixtureIngestionAdapter", "IngestionAdapter"]
