"""Purpose: Validate evidence-citing structured alert triage responses."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class TriageValidationError(ValueError):
    """Represent provider output that cannot be safely used as triage."""

    code = "invalid_triage_response"


class ObservedFact(BaseModel):
    """Represent an observed claim and the evidence supporting it."""

    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class AlertTriageOutput(BaseModel):
    """Represent the versioned, advisory alert-triage response contract."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="v1", min_length=1)
    summary: str = Field(min_length=1)
    observed_facts: list[ObservedFact] = Field(default_factory=list)
    assessment: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    missing_information: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(min_length=1)

    @field_validator("evidence_refs")
    @classmethod
    def reject_duplicate_evidence_refs(cls, value: list[str]) -> list[str]:
        """Reject duplicate top-level references instead of silently normalizing them."""
        if len(value) != len(set(value)):
            raise ValueError("evidence_refs must not contain duplicates")
        return value

    @model_validator(mode="after")
    def require_facts_when_citing(self) -> "AlertTriageOutput":
        """Require observed facts to carry their own citations when present."""
        for fact in self.observed_facts:
            if len(fact.evidence_ids) != len(set(fact.evidence_ids)):
                raise ValueError("observed fact evidence_ids must not contain duplicates")
        return self


def validate_triage_output(raw: str | dict[str, Any], valid_evidence_ids: set[str] | frozenset[str]) -> AlertTriageOutput:
    """Parse and validate provider output against the current context IDs."""
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
        result = AlertTriageOutput.model_validate(payload)
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        if isinstance(error, TriageValidationError):
            raise
        message = "Provider output did not match the triage schema."
        if isinstance(error, ValidationError) and "duplicates" in str(error):
            message = "Provider output contained duplicate evidence IDs (duplicates are not allowed)."
        raise TriageValidationError(message) from error
    cited_ids = list(result.evidence_refs)
    cited_ids.extend(evidence_id for fact in result.observed_facts for evidence_id in fact.evidence_ids)
    unsupported = sorted(set(cited_ids) - set(valid_evidence_ids))
    if unsupported:
        raise TriageValidationError(
            f"Provider output cited evidence outside the supplied context: {unsupported}."
        )
    return result
