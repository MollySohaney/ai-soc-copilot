"""Purpose: Define shared enumerations used across SOC data models."""

from __future__ import annotations

import enum


class SeverityEnum(str, enum.Enum):
    """Represent the severity level of an alert or detection rule."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatusEnum(str, enum.Enum):
    """Represent the triage status of an alert."""

    NEW = "new"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"
    FALSE_POSITIVE = "false_positive"


class CaseStatusEnum(str, enum.Enum):
    """Represent the workflow status of an investigation case."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class CasePriorityEnum(str, enum.Enum):
    """Represent the priority level of an investigation case."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
