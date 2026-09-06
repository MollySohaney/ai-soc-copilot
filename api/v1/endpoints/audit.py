"""Purpose: Expose bounded Admin-only reads of immutable audit events."""

from __future__ import annotations

import math
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.schemas.audit import AuditEventRead, PaginatedAuditEvents
from backend.security.rbac import Permission
from db.models import AuditEvent
from db.session import get_db

router = APIRouter(
    prefix="/audit-events",
    tags=["audit"],
    dependencies=[Depends(require_permission(Permission.READ_AUDIT))],
)


@router.get("", response_model=PaginatedAuditEvents)
def list_audit_events(
    actor_user_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    target_type: str | None = Query(default=None, min_length=1, max_length=100),
    target_id: str | None = Query(default=None, min_length=1, max_length=255),
    outcome: str | None = Query(default=None, pattern="^(succeeded|failed|denied)$"),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedAuditEvents:
    """List sanitized events using exact indexed filters."""
    filters = []
    if actor_user_id is not None:
        filters.append(AuditEvent.actor_user_id == actor_user_id)
    if action is not None:
        filters.append(AuditEvent.action == action)
    if target_type is not None:
        filters.append(AuditEvent.target_type == target_type)
    if target_id is not None:
        filters.append(AuditEvent.target_id == target_id)
    if outcome is not None:
        filters.append(AuditEvent.outcome == outcome)
    if start_time is not None:
        filters.append(AuditEvent.occurred_at >= start_time)
    if end_time is not None:
        filters.append(AuditEvent.occurred_at < end_time)

    total = db.scalar(select(func.count()).select_from(AuditEvent).where(*filters)) or 0
    events = db.scalars(
        select(AuditEvent)
        .where(*filters)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedAuditEvents(
        items=[AuditEventRead.model_validate(event) for event in events],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
