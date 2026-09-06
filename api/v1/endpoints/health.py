"""Purpose: Expose a health check endpoint for the API service."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from config.settings import load_config
from db.session import get_db

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


@router.get("/ready")
def get_readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Verify database connectivity without exposing dependency details."""
    settings = load_config()
    try:
        db.execute(text("SELECT 1"))
    except Exception as error:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready.",
        ) from error
    return {
        "status": "ready",
        "app_name": settings.app_name,
        "api_version": settings.api_version,
    }
