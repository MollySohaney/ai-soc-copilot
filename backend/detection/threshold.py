"""Deterministic threshold evaluation over event-time tumbling windows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from backend.detection.dsl import DetectionLogic
from backend.detection.matcher import match_event


@dataclass(frozen=True)
class ThresholdMatch:
    """One threshold firing and its complete evidence set."""

    group: dict[str, Any]
    count: int
    window_start: datetime
    window_end: datetime
    evidence_event_ids: tuple[str, ...]


def _field(event: object, name: str) -> Any:
    if isinstance(event, Mapping):
        return event.get(name)
    accessors = {
        "event_id": lambda item: item.event_id, "timestamp": lambda item: item.timestamp,
        "source_ip": lambda item: item.source_ip, "username": lambda item: item.username,
        "hostname": lambda item: item.hostname,
    }
    try:
        return accessors[name](event)
    except (KeyError, AttributeError):
        return None


def _event_time(event: object) -> datetime:
    value = _field(event, "timestamp")
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("events must have timezone-aware timestamp values")
    return value.astimezone(timezone.utc)


def evaluate_threshold(
    events: Iterable[object], logic: DetectionLogic, window_start: datetime, window_end: datetime
) -> list[ThresholdMatch]:
    """Evaluate a threshold rule using fixed tumbling `[start, end)` windows.

    The supplied run window is partitioned from ``window_start`` into windows
    of ``logic.window_seconds``. Events exactly at the run end are excluded.
    Events missing a group key are excluded rather than combined in a NULL
    bucket. Results and evidence are sorted deterministically.
    """
    if logic.rule_type != "threshold" or logic.condition is None:
        raise ValueError("evaluate_threshold requires threshold DetectionLogic")
    if window_start.tzinfo is None or window_end.tzinfo is None or window_end <= window_start:
        raise ValueError("window bounds must be ordered and timezone-aware")
    start = window_start.astimezone(timezone.utc)
    end = window_end.astimezone(timezone.utc)
    duration = timedelta(seconds=logic.window_seconds or 0)
    buckets: dict[tuple[datetime, tuple[tuple[str, Any], ...]], list[object]] = {}
    for event in events:
        timestamp = _event_time(event)
        if timestamp < start or timestamp >= end or not match_event(event, logic.condition).matched:
            continue
        group_values = {key: _field(event, key) for key in logic.group_by}
        if any(value is None for value in group_values.values()):
            continue
        bucket_start = start + ((timestamp - start) // duration) * duration
        key = (bucket_start, tuple(group_values.items()))
        buckets.setdefault(key, []).append(event)

    matches = []
    for (bucket_start, group_items), bucket_events in sorted(
        buckets.items(), key=lambda item: (item[0][0], repr(item[0][1]))
    ):
        ordered = sorted(bucket_events, key=lambda item: (_event_time(item), str(_field(item, "event_id"))))
        if logic.distinct_count_field:
            values = {_field(event, logic.distinct_count_field) for event in ordered}
            count = len({value for value in values if value is not None})
        else:
            count = len(ordered)
        if count < (logic.min_count or 0):
            continue
        bucket_end = min(bucket_start + duration, end)
        matches.append(
            ThresholdMatch(
                group=dict(group_items), count=count, window_start=bucket_start,
                window_end=bucket_end,
                evidence_event_ids=tuple(str(_field(event, "event_id")) for event in ordered),
            )
        )
    return matches


class ThresholdEvaluator:
    """Small object wrapper for callers that prefer an evaluator instance."""

    def evaluate(self, events: Iterable[object], logic: DetectionLogic, window_start: datetime, window_end: datetime) -> list[ThresholdMatch]:
        return evaluate_threshold(events, logic, window_start, window_end)


__all__ = ["ThresholdMatch", "ThresholdEvaluator", "evaluate_threshold"]
