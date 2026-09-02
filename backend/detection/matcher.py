"""Pure single-event evaluation for the structured detection DSL."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from typing import Any, Mapping

from backend.detection.dsl import Condition


@dataclass(frozen=True)
class MatchExplanation:
    """Stable, recursively renderable explanation of one evaluation."""

    matched: bool
    operator: str
    field: str | None = None
    expected: Any = None
    actual: Any = None
    missing: bool = False
    children: tuple["MatchExplanation", ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible explanation tree."""
        result: dict[str, Any] = {
            "matched": self.matched,
            "operator": self.operator,
        }
        if self.field is not None:
            result.update(field=self.field, expected=self.expected, actual=self.actual, missing=self.missing)
        if self.children:
            result["children"] = [child.to_dict() for child in self.children]
        return result

    def render(self, indent: int = 0) -> str:
        """Render the explanation as deterministic analyst-readable text."""
        prefix = " " * indent
        outcome = "matched" if self.matched else "did not match"
        if self.field is not None:
            line = f"{prefix}{self.field} {self.operator} {self.expected!r} ({outcome}; actual={self.actual!r})"
        else:
            line = f"{prefix}{self.operator} ({outcome})"
        return "\n".join([line, *(child.render(indent + 2) for child in self.children)])


@dataclass(frozen=True)
class MatchResult:
    """Matcher result that supports both named access and tuple unpacking."""

    matched: bool
    explanation: MatchExplanation

    def __iter__(self):
        yield self.matched
        yield self.explanation


def _value(event: object, field: str) -> tuple[Any, bool]:
    """Read a validated Event field from a mapping or plain object."""
    if isinstance(event, Mapping):
        value = event.get(field)
    else:
        # This is intentionally a fixed whitelist, not user-controlled attribute dispatch.
        accessors = {
            "event_id": lambda item: item.event_id, "timestamp": lambda item: item.timestamp,
            "ingested_at": lambda item: item.ingested_at, "source": lambda item: item.source,
            "dataset": lambda item: item.dataset, "event_category": lambda item: item.event_category,
            "event_action": lambda item: item.event_action, "event_outcome": lambda item: item.event_outcome,
            "message": lambda item: item.message, "severity": lambda item: item.severity,
            "source_ip": lambda item: item.source_ip, "source_port": lambda item: item.source_port,
            "destination_ip": lambda item: item.destination_ip, "destination_port": lambda item: item.destination_port,
            "hostname": lambda item: item.hostname, "username": lambda item: item.username,
            "process_name": lambda item: item.process_name, "process_command_line": lambda item: item.process_command_line,
            "file_path": lambda item: item.file_path, "normalization_version": lambda item: item.normalization_version,
        }
        try:
            value = accessors[field](event)
        except (AttributeError, KeyError):
            value = None
    return value, value is None


def _utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _leaf(event: object, condition: Condition) -> MatchExplanation:
    actual, missing = _value(event, condition.field)  # type: ignore[arg-type]
    operator = condition.operator
    if operator == "exists":
        matched = not missing
    elif operator == "not_exists":
        matched = missing
    elif missing:
        # Missing not_equals is deliberately false; only not_exists asserts absence.
        matched = False
    else:
        expected = condition.value
        try:
            if operator == "equals": matched = type(actual) is type(expected) and actual == expected
            elif operator == "not_equals": matched = type(actual) is type(expected) and actual != expected
            elif operator == "contains": matched = isinstance(actual, str) and expected in actual
            elif operator == "not_contains": matched = isinstance(actual, str) and expected not in actual
            elif operator == "starts_with": matched = isinstance(actual, str) and actual.startswith(expected)
            elif operator == "ends_with": matched = isinstance(actual, str) and actual.endswith(expected)
            elif operator == "in": matched = any(type(actual) is type(item) and actual == item for item in expected)
            elif operator == "not_in": matched = not any(type(actual) is type(item) and actual == item for item in expected)
            elif operator in {"gt", "gte", "lt", "lte"}:
                if not isinstance(actual, (int, float)) or isinstance(actual, bool): matched = False
                elif operator == "gt": matched = actual > expected
                elif operator == "gte": matched = actual >= expected
                elif operator == "lt": matched = actual < expected
                else: matched = actual <= expected
            elif operator in {"before", "after", "on_or_before", "on_or_after"}:
                left, right = _utc(actual), _utc(expected)
                matched = {"before": left < right, "after": left > right, "on_or_before": left <= right, "on_or_after": left >= right}[operator]
            elif operator == "cidr_match": matched = ip_address(actual) in ip_network(expected, strict=False)
            else: matched = False
        except (TypeError, ValueError):
            matched = False
    return MatchExplanation(matched, operator, condition.field, condition.value, actual, missing)


def match_event(event: object, condition: Condition) -> MatchResult:
    """Evaluate one event without I/O, database access, or global state."""
    if condition.operator not in {"and", "or", "not"}:
        explanation = _leaf(event, condition)
    else:
        children = tuple(match_event(event, child).explanation for child in condition.children)
        if condition.operator == "and": matched = all(child.matched for child in children)
        elif condition.operator == "or": matched = any(child.matched for child in children)
        else: matched = not children[0].matched if not children[0].missing else False
        explanation = MatchExplanation(
            matched, condition.operator, missing=any(child.missing for child in children), children=children
        )
    return MatchResult(explanation.matched, explanation)


evaluate_condition = match_event

__all__ = ["MatchExplanation", "MatchResult", "match_event", "evaluate_condition"]
