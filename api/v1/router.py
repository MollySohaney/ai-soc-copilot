"""Purpose: Aggregate v1 API endpoint routers."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.dependencies.auth import require_authenticated_user
from api.v1.endpoints import admin, ai, alerts, auth, cases, copilot, dashboard, events, health, ingestion, reports, rules

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)

protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])
protected_router.include_router(events.router)
protected_router.include_router(alerts.router)
protected_router.include_router(cases.router)
protected_router.include_router(dashboard.router)
protected_router.include_router(rules.router)
protected_router.include_router(ingestion.router)
protected_router.include_router(ai.router)
protected_router.include_router(copilot.router)
protected_router.include_router(reports.router)
protected_router.include_router(admin.router)
api_router.include_router(protected_router)
