"""Purpose: Share bounded date-window validation across query endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import HTTPException, Path

PositiveId = Annotated[int, Path(gt=0)]
ProviderName = Annotated[
    str, Path(min_length=1, max_length=32, pattern=r"^[a-z][a-z0-9_-]*$")
]


def validate_time_window(
    start: datetime | None,
    end: datetime | None,
    *,
    max_days: int,
) -> None:
    """Reject inverted, naive, or excessively broad explicit time windows."""
    if (start is None) != (end is None):
        raise HTTPException(
            status_code=422,
            detail="start_time and end_time must be provided together.",
        )
    for value in (start, end):
        if value is not None and value.tzinfo is None:
            raise HTTPException(status_code=422, detail="Timestamps must include a timezone.")
    if start is not None and end is not None:
        if end <= start:
            raise HTTPException(status_code=422, detail="end_time must be after start_time.")
        if end - start > timedelta(days=max_days):
            raise HTTPException(
                status_code=422,
                detail=f"Time window must not exceed {max_days} days.",
            )


def validate_timestamp(value: datetime | None) -> None:
    """Reject ambiguous timestamps that omit a UTC offset."""
    if value is not None and value.tzinfo is None:
        raise HTTPException(status_code=422, detail="Timestamps must include a timezone.")
