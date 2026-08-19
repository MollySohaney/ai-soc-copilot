"""Purpose: Expose a health check endpoint for the API service."""

from __future__ import annotations

from fastapi import APIRouter

from config.settings import load_config

router = APIRouter()


@router.get("/health")
def get_health() -> dict[str, str]:
    """Report the API service health status.

    Returns:
        Service health status and identifying metadata.
    """
    settings = load_config()
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "api_version": settings.api_version,
    }
