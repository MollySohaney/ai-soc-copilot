"""Purpose: Define request/response DTOs for case activity timeline entries."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CaseActivityBase(BaseModel):
    """Represent the shared fields for a case activity entry."""

    case_id: int
    activity_type: str
    message: str
    author: str | None = None


class CaseActivityCreate(CaseActivityBase):
    """Represent the payload required to create a case activity entry."""


class CaseActivityRead(CaseActivityBase):
    """Represent a case activity entry as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
