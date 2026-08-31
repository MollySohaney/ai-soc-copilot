"""Purpose: Define request/response DTOs for detection rules."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from db.models.enums import SeverityEnum

DetectionRuleLanguage = Literal["sigma", "kql", "spl", "yara", "custom"]

MITRE_TECHNIQUE_ID_PATTERN = re.compile(r"^T\d{4}(\.\d{3})?$")

# The 14 canonical MITRE ATT&CK Enterprise tactic names.
MITRE_TACTICS = {
    "Reconnaissance",
    "Resource Development",
    "Initial Access",
    "Execution",
    "Persistence",
    "Privilege Escalation",
    "Defense Evasion",
    "Credential Access",
    "Discovery",
    "Lateral Movement",
    "Collection",
    "Command and Control",
    "Exfiltration",
    "Impact",
}


def _validate_mitre_tactic(value: str | None) -> str | None:
    """Validate that a MITRE tactic name is one of the 14 canonical Enterprise tactics.

    Args:
        value: The tactic name to validate, or None.

    Returns:
        The unchanged value.

    Raises:
        ValueError: If the value is set and is not a canonical MITRE ATT&CK tactic name.
    """
    if value is not None and value not in MITRE_TACTICS:
        raise ValueError(
            f"mitre_tactic must be one of the 14 canonical MITRE ATT&CK tactics: {value!r}"
        )
    return value


def _validate_mitre_technique_id(value: str | None) -> str | None:
    """Validate that a MITRE technique id matches the expected format.

    Args:
        value: The technique id to validate, or None.

    Returns:
        The unchanged value.

    Raises:
        ValueError: If the value is set and does not match the pattern Txxxx or Txxxx.xxx.
    """
    if value is not None and not MITRE_TECHNIQUE_ID_PATTERN.match(value):
        raise ValueError(f"mitre_technique_id must match ^T\\d{{4}}(\\.\\d{{3}})?$: {value!r}")
    return value


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

    language: DetectionRuleLanguage
    risk_score: int | None = Field(default=None, ge=0, le=100)

    _validate_mitre_tactic = field_validator("mitre_tactic")(_validate_mitre_tactic)
    _validate_mitre_technique_id = field_validator("mitre_technique_id")(
        _validate_mitre_technique_id
    )


class DetectionRuleUpdate(BaseModel):
    """Represent a partial update payload for a detection rule."""

    name: str | None = None
    description: str | None = None
    source: str | None = None
    language: DetectionRuleLanguage | None = None
    query: str | None = None
    severity: SeverityEnum | None = None
    risk_score: int | None = Field(default=None, ge=0, le=100)
    enabled: bool | None = None
    mitre_tactic: str | None = None
    mitre_technique_id: str | None = None
    mitre_technique_name: str | None = None

    _validate_mitre_tactic = field_validator("mitre_tactic")(_validate_mitre_tactic)
    _validate_mitre_technique_id = field_validator("mitre_technique_id")(
        _validate_mitre_technique_id
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_non_nullable_fields(cls, data: Any) -> Any:
        """Reject explicit nulls for rule fields that cannot be cleared."""
        if isinstance(data, dict):
            null_fields = sorted(
                field
                for field in ("name", "query", "severity", "enabled")
                if field in data and data[field] is None
            )
            if null_fields:
                raise ValueError(f"{', '.join(null_fields)} cannot be null")
        return data


class DetectionRuleRead(DetectionRuleBase):
    """Represent a detection rule as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class PaginatedDetectionRules(BaseModel):
    """Represent a page of detection rules."""

    items: list[DetectionRuleRead]
    total: int
    page: int
    page_size: int
    total_pages: int
