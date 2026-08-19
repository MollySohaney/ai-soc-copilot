"""Purpose: Expose a typed HTTP client layer for the SOC API, for use by the Streamlit frontend."""

from __future__ import annotations

from api_client.http import ApiClientError, build_client

__all__ = ["ApiClientError", "build_client"]
