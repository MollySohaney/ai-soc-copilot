"""Purpose: Define sanitized errors raised by ingestion adapters."""

from __future__ import annotations


class IngestionAdapterError(RuntimeError):
    """Base class for provider-neutral ingestion adapter failures."""


class IngestionConfigurationError(IngestionAdapterError):
    """Raised when an adapter is missing required non-secret configuration."""


class IngestionAuthenticationError(IngestionAdapterError):
    """Raised when a provider rejects configured credentials."""


class IngestionTimeoutError(IngestionAdapterError):
    """Raised when a provider request exceeds the configured timeout."""


class IngestionConnectionError(IngestionAdapterError):
    """Raised when a provider cannot be reached."""
