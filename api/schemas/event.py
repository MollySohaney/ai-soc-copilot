"""Purpose: Define request/response DTOs for telemetry events."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    """Represent the shared fields for a telemetry event."""

    event_id: str
    timestamp: datetime
    source: str
    dataset: str | None = None
    event_category: str | None = None
    event_action: str | None = None
    event_outcome: str | None = None
    message: str | None = None
    severity: str | None = None
    source_ip: str | None = None
    source_port: int | None = None
    destination_ip: str | None = None
    destination_port: int | None = None
    hostname: str | None = None
    username: str | None = None
    process_name: str | None = None
    process_command_line: str | None = None
    file_path: str | None = None
    raw_event: dict[str, Any] | None = None


class EventCreate(EventBase):
    """Represent the payload required to create a telemetry event."""


class EventRead(EventBase):
    """Represent a telemetry event as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ingested_at: datetime
