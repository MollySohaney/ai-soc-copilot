"""Bounded ordered multi-stage sequence correlation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from backend.detection.dsl import DetectionLogic, SequenceStage
from backend.detection.matcher import match_event


@dataclass(frozen=True)
class SequenceMatch:
    """One ordered chain with shared correlation values and stage evidence."""

    correlation: dict[str, Any]
    span: timedelta
    stage_evidence: dict[str, tuple[str, ...]]


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


def _time(event: object) -> datetime:
    value = _field(event, "timestamp")
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("events must have timezone-aware timestamp values")
    return value.astimezone(timezone.utc)


def _stage_label(stage: SequenceStage, index: int) -> str:
    return stage.label or f"stage_{index + 1}"


def evaluate_sequence(events: Iterable[object], logic: DetectionLogic) -> list[SequenceMatch]:
    """Evaluate a sequence with earliest-match-per-stage semantics.

    Events between stages do not break a chain. Each stage chooses the first
    subsequent matching event (or the first ``min_count`` such events), with
    all shared keys equal to the first-stage values. A chain's span is measured
    from the first event through the last event and must be no greater than
    ``max_span_seconds``. Results are deduplicated by their exact evidence.
    """
    if logic.rule_type != "sequence" or not logic.stages or logic.max_span_seconds is None:
        raise ValueError("evaluate_sequence requires sequence DetectionLogic")
    ordered = sorted(events, key=lambda item: (_time(item), str(_field(item, "event_id"))))
    results: list[SequenceMatch] = []
    seen: set[tuple[tuple[str, tuple[str, ...]], ...]] = set()
    max_span = timedelta(seconds=logic.max_span_seconds)
    for start_index, first in enumerate(ordered):
        first_stage = logic.stages[0]
        if not match_event(first, first_stage.condition).matched:
            continue
        correlation = {key: _field(first, key) for key in logic.shared_keys}
        if any(value is None for value in correlation.values()):
            continue
        first_events: list[object] = [first]
        cursor = start_index + 1
        while cursor < len(ordered) and len(first_events) < first_stage.min_count:
            candidate = ordered[cursor]
            cursor += 1
            if _time(candidate) - _time(first) > max_span:
                break
            if any(_field(candidate, key) != value for key, value in correlation.items()):
                continue
            if any(_field(candidate, key) is None for key in logic.shared_keys):
                continue
            if match_event(candidate, first_stage.condition).matched:
                first_events.append(candidate)
        if len(first_events) < first_stage.min_count:
            continue
        selected: list[list[object]] = [first_events]
        valid = True
        for stage in logic.stages[1:]:
            stage_events: list[object] = []
            while cursor < len(ordered) and len(stage_events) < stage.min_count:
                candidate = ordered[cursor]
                cursor += 1
                if _time(candidate) - _time(first) > max_span:
                    break
                if any(_field(candidate, key) != value for key, value in correlation.items()):
                    continue
                if any(_field(candidate, key) is None for key in logic.shared_keys):
                    continue
                if match_event(candidate, stage.condition).matched:
                    stage_events.append(candidate)
            if len(stage_events) < stage.min_count:
                valid = False
                break
            selected.append(stage_events)
        if not valid:
            continue
        last = selected[-1][-1]
        if _time(last) - _time(first) > max_span:
            continue
        evidence = {
            _stage_label(stage, index): tuple(str(_field(item, "event_id")) for item in stage_events)
            for index, (stage, stage_events) in enumerate(zip(logic.stages, selected))
        }
        identity = tuple(sorted(evidence.items()))
        if identity in seen:
            continue
        seen.add(identity)
        results.append(SequenceMatch(correlation, _time(last) - _time(first), evidence))
    return results


class SequenceEvaluator:
    """Object wrapper for sequence evaluation callers."""

    def evaluate(self, events: Iterable[object], logic: DetectionLogic) -> list[SequenceMatch]:
        return evaluate_sequence(events, logic)


__all__ = ["SequenceMatch", "SequenceEvaluator", "evaluate_sequence"]
