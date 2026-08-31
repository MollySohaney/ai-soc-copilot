"""Purpose: Expose Pydantic request/response DTOs for the HTTP API."""

from __future__ import annotations

from api.schemas.alert import (
    AlertCreate,
    AlertEventsRead,
    AlertRead,
    AlertUpdate,
    PaginatedAlerts,
)
from api.schemas.case import CaseCreate, CaseRead
from api.schemas.case_activity import CaseActivityCreate, CaseActivityRead
from api.schemas.detection_rule import DetectionRuleCreate, DetectionRuleRead
from api.schemas.event import EventCreate, EventRead, PaginatedEvents
from api.schemas.ingestion import (
    IngestionCheckpointRead,
    IngestionConnectionTestRequest,
    IngestionConnectionTestResponse,
    IngestionRunHistory,
    IngestionRunRead,
    IngestionStatusResponse,
    IngestionSyncRequest,
    IngestionSyncResponse,
)

__all__ = [
    "AlertCreate",
    "AlertEventsRead",
    "AlertRead",
    "AlertUpdate",
    "PaginatedAlerts",
    "CaseCreate",
    "CaseRead",
    "CaseActivityCreate",
    "CaseActivityRead",
    "DetectionRuleCreate",
    "DetectionRuleRead",
    "EventCreate",
    "EventRead",
    "PaginatedEvents",
    "IngestionCheckpointRead",
    "IngestionConnectionTestRequest",
    "IngestionConnectionTestResponse",
    "IngestionRunHistory",
    "IngestionRunRead",
    "IngestionStatusResponse",
    "IngestionSyncRequest",
    "IngestionSyncResponse",
]
