"""Purpose: Aggregate v1 API endpoint routers."""

from __future__ import annotations

from fastapi import APIRouter

from api.v1.endpoints import ai, alerts, cases, copilot, dashboard, events, health, ingestion, reports, rules

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(events.router)
api_router.include_router(alerts.router)
api_router.include_router(cases.router)
api_router.include_router(dashboard.router)
api_router.include_router(rules.router)
api_router.include_router(ingestion.router)
api_router.include_router(ai.router)
api_router.include_router(copilot.router)
api_router.include_router(reports.router)
