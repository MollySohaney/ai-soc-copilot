"""Purpose: Define the evidence-grounded report draft contract."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportDraftOutput(BaseModel):
    """Represent a reviewable report draft generated from confirmed case content."""

    model_config = ConfigDict(extra="forbid")

    executive_summary: str = Field(min_length=1)
    technical_timeline: list[dict[str, Any]] = Field(default_factory=list)
    indicators: list[dict[str, Any]] = Field(default_factory=list)
    mitre: list[dict[str, Any]] = Field(default_factory=list)
    actions_recorded: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(min_length=1)
