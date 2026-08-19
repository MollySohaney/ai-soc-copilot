"""Purpose: Define request/response DTOs for investigation cases."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from db.models.enums import CasePriorityEnum, CaseStatusEnum


class CaseBase(BaseModel):
    """Represent the shared fields for an investigation case."""

    case_number: str
    title: str
    description: str | None = None
    status: CaseStatusEnum = CaseStatusEnum.OPEN
    priority: CasePriorityEnum = CasePriorityEnum.MEDIUM
    assignee: str | None = None


class CaseCreate(CaseBase):
    """Represent the payload required to create an investigation case."""


class CaseRead(CaseBase):
    """Represent an investigation case as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
