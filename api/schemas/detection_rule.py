"""Purpose: Define request/response DTOs for detection rules."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from db.models.enums import SeverityEnum


class DetectionRuleBase(BaseModel):
    """Represent the shared fields for a detection rule."""

    name: str
    description: str | None = None
    source: str | None = None
    language: str | None = None
    query: str
    severity: SeverityEnum
    risk_score: int | None = None
    enabled: bool = True
    mitre_tactic: str | None = None
    mitre_technique_id: str | None = None
    mitre_technique_name: str | None = None


class DetectionRuleCreate(DetectionRuleBase):
    """Represent the payload required to create a detection rule."""


class DetectionRuleRead(DetectionRuleBase):
    """Represent a detection rule as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
