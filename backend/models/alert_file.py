"""Purpose: Define normalized models for uploaded alert artifacts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AlertPreview(BaseModel):
    """Represent parsed alert preview data for the UI."""

    metadata: dict[str, Any] = Field(default_factory=dict)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    text_preview: str | None = None


class UploadResult(BaseModel):
    """Represent the outcome of an uploaded alert validation workflow."""

    is_valid: bool
    message: str
    preview: AlertPreview = Field(default_factory=AlertPreview)
