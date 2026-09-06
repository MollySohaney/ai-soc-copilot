"""Purpose: Define bounded, read-only security audit response contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    """Expose already-redacted immutable audit fields."""

    model_config = ConfigDict(from_attributes=True)

    event_id: str
    occurred_at: datetime
    actor_user_id: int | None
    actor_type: str
    actor_identifier: str | None
    action: str
    target_type: str | None
    target_id: str | None
    outcome: str
    request_id: str | None
    source_ip: str | None
    source_context: dict | None
    before_state: dict | None
    after_state: dict | None
    details: dict | None


class PaginatedAuditEvents(BaseModel):
    """Return a bounded page of audit events."""

    items: list[AuditEventRead]
    total: int
    page: int
    page_size: int
    total_pages: int
