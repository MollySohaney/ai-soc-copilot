"""Purpose: Re-export the declarative base and all ORM models for Alembic autogeneration."""

from __future__ import annotations

from db.base import Base
from db.models.alert import Alert, alert_event
from db.models.ai_analysis import AIAnalysis
from db.models.case import Case
from db.models.case_activity import CaseActivity
from db.models.case_alert import CaseAlert
from db.models.detection_rule import DetectionRule, DetectionRuleVersion
from db.models.detection_run import DetectionRun
from db.models.enums import AlertStatusEnum, CasePriorityEnum, CaseStatusEnum, SeverityEnum
from db.models.event import Event
from db.models.ingestion import IngestionCheckpoint, IngestionRun
from db.models.user import AuthSession, RoleEnum, User

__all__ = [
    "Base",
    "Alert",
    "AIAnalysis",
    "alert_event",
    "Case",
    "CaseActivity",
    "CaseAlert",
    "DetectionRule",
    "DetectionRuleVersion",
    "DetectionRun",
    "AlertStatusEnum",
    "CasePriorityEnum",
    "CaseStatusEnum",
    "SeverityEnum",
    "Event",
    "IngestionCheckpoint",
    "IngestionRun",
    "AuthSession",
    "RoleEnum",
    "User",
]
