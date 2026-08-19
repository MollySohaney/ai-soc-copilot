"""Purpose: Aggregate v1 API endpoint routers."""

from __future__ import annotations

from fastapi import APIRouter

from api.v1.endpoints import health

api_router = APIRouter()
api_router.include_router(health.router)
