"""Purpose: Define dashboard-oriented view models."""

from __future__ import annotations

from pydantic import BaseModel


class DashboardMetric(BaseModel):
    """Represent a single dashboard metric card."""

    label: str
    value: str
    delta: str | None = None
