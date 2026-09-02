"""Purpose: Define request/response DTOs for alerts."""

from __future__ import annotations

from datetime import datetime

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.schemas.event import EventRead
from db.models.enums import AlertStatusEnum, SeverityEnum


class AlertBase(BaseModel):
    """Represent the shared fields for an alert."""

    external_id: str | None = None
    title: str
    description: str | None = None
    severity: SeverityEnum
    risk_score: int | None = None
    status: AlertStatusEnum = AlertStatusEnum.NEW
    source: str | None = None
    rule_id: str | None = None
    detection_rule_id: int | None = None
    rule_version: int | None = None
    detection_run_id: int | None = None
    fingerprint: str | None = None
    rule_logic_snapshot: dict | None = None
    match_explanation: dict | None = None
    hostname: str | None = None
    username: str | None = None
    source_ip: str | None = None
    destination_ip: str | None = None
    mitre_tactic: str | None = None
    mitre_technique_id: str | None = None
    mitre_technique_name: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class AlertCreate(AlertBase):
    """Represent the payload required to create an alert."""


class AlertRead(AlertBase):
    """Represent an alert as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AlertUpdate(BaseModel):
    """Represent a partial update payload for an alert."""

    status: AlertStatusEnum | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, data: Any) -> Any:
        """Reject explicit nulls for alert fields that cannot be cleared."""
        if isinstance(data, dict) and data.get("status") is None and "status" in data:
            raise ValueError("status cannot be null")
        return data


class PaginatedAlerts(BaseModel):
    """Represent a page of alerts."""

    items: list[AlertRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class AlertEventsRead(BaseModel):
    """Represent the events linked to an alert."""

    items: list[EventRead]
    total: int
