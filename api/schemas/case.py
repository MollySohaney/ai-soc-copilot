"""Purpose: Define request/response DTOs for investigation cases."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from api.schemas.alert import AlertRead
from api.schemas.case_activity import CaseActivityRead
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


class CaseCreateRequest(BaseModel):
    """Represent the payload required to create an investigation case via the API."""

    title: str
    description: str | None = None
    priority: CasePriorityEnum = CasePriorityEnum.MEDIUM
    status: CaseStatusEnum = CaseStatusEnum.OPEN
    assignee: str | None = None
    alert_ids: list[int] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    """Represent a partial update payload for an investigation case."""

    title: str | None = None
    description: str | None = None
    status: CaseStatusEnum | None = None
    priority: CasePriorityEnum | None = None
    assignee: str | None = None


class CaseDetail(CaseRead):
    """Represent an investigation case with its linked alerts and activity timeline."""

    alerts: list[AlertRead]
    activities: list[CaseActivityRead]


class PaginatedCases(BaseModel):
    """Represent a page of investigation cases."""

    items: list[CaseRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class CaseAlertsAddRequest(BaseModel):
    """Represent the payload required to link alerts to an investigation case."""

    alert_ids: list[int] = Field(min_length=1)
