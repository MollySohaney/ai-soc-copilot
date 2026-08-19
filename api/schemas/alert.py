"""Purpose: Define request/response DTOs for alerts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
