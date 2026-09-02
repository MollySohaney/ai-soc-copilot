"""Validation models for the structured detection DSL.

The DSL is deliberately data-only. Consumers dispatch on the validated
operator values and never turn rule input into Python, SQL, or shell code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DSL_VERSION = "1"
MAX_NESTING_DEPTH = 8
MAX_PREDICATES = 100
MAX_IN_LIST_LENGTH = 100
MAX_SEQUENCE_STAGES = 8
MAX_WINDOW_SECONDS = 86_400

EVENT_FIELDS = frozenset(
    {
        "event_id", "timestamp", "ingested_at", "source", "dataset", "event_category",
        "event_action", "event_outcome", "message", "severity", "source_ip", "source_port",
        "destination_ip", "destination_port", "hostname", "username", "process_name",
        "process_command_line", "file_path", "normalization_version",
    }
)
LEAF_OPERATORS = frozenset(
    {
        "equals", "not_equals", "contains", "not_contains", "starts_with", "ends_with",
        "exists", "not_exists", "in", "not_in", "gt", "gte", "lt", "lte",
        "before", "after", "on_or_before", "on_or_after", "cidr_match",
    }
)
BOOLEAN_OPERATORS = frozenset({"and", "or", "not"})
NUMERIC_OPERATORS = frozenset({"gt", "gte", "lt", "lte"})
TIME_OPERATORS = frozenset({"before", "after", "on_or_before", "on_or_after"})


class Condition(BaseModel):
    """Represent one boolean group or one safe field predicate."""

    model_config = ConfigDict(extra="forbid")

    operator: str
    field: str | None = None
    value: Any = None
    children: list["Condition"] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_shape(self) -> "Condition":
        """Enforce the operator-specific shape and bounded tree limits."""
        if self.operator in BOOLEAN_OPERATORS:
            if self.field is not None or self.value is not None:
                raise ValueError(f"boolean operator {self.operator!r} cannot have field/value")
            if not self.children or (self.operator == "not" and len(self.children) != 1):
                expected = "exactly one child" if self.operator == "not" else "at least one child"
                raise ValueError(f"{self.operator!r} requires {expected}")
            _validate_tree_limits(self)
            return self
        if self.operator not in LEAF_OPERATORS:
            raise ValueError(f"unknown operator {self.operator!r}")
        if self.children:
            raise ValueError(f"leaf operator {self.operator!r} cannot have children")
        if self.field is None or self.field not in EVENT_FIELDS:
            raise ValueError(
                f"field must be one of the whitelisted Event fields; got {self.field!r}"
            )
        if self.operator in {"exists", "not_exists"}:
            if self.value is not None:
                raise ValueError(f"{self.operator} does not accept a value")
        elif self.value is None:
            raise ValueError(f"operator {self.operator!r} requires a value")
        if self.operator in NUMERIC_OPERATORS and not isinstance(self.value, (int, float)):
            raise ValueError(f"operator {self.operator!r} requires a numeric value")
        if self.operator in TIME_OPERATORS:
            if not isinstance(self.value, datetime):
                raise ValueError(f"operator {self.operator!r} requires a datetime value")
            if self.value.tzinfo is None:
                raise ValueError("time comparison values must be timezone-aware")
        if self.operator in {"in", "not_in"}:
            if not isinstance(self.value, list) or not self.value:
                raise ValueError(f"operator {self.operator!r} requires a non-empty list")
            if len(self.value) > MAX_IN_LIST_LENGTH:
                raise ValueError(f"membership lists may contain at most {MAX_IN_LIST_LENGTH} values")
        if self.operator in {"contains", "not_contains", "starts_with", "ends_with", "cidr_match"}:
            if not isinstance(self.value, str):
                raise ValueError(f"operator {self.operator!r} requires a string value")
        return self


Condition.model_rebuild()


def _validate_tree_limits(condition: Condition, depth: int = 1) -> int:
    """Return predicate count while enforcing depth and predicate limits."""
    if depth > MAX_NESTING_DEPTH:
        raise ValueError(f"condition nesting exceeds maximum depth {MAX_NESTING_DEPTH}")
    if not condition.children:
        return 1
    total = sum(_validate_tree_limits(child, depth + 1) for child in condition.children)
    if total > MAX_PREDICATES:
        raise ValueError(f"condition tree may contain at most {MAX_PREDICATES} predicates")
    return total


class SequenceStage(BaseModel):
    """Represent one ordered stage in a sequence rule."""

    model_config = ConfigDict(extra="forbid")

    condition: Condition
    label: str | None = Field(default=None, min_length=1, max_length=100)
    min_count: int = Field(default=1, ge=1, le=MAX_PREDICATES)


class DetectionLogic(BaseModel):
    """Represent a complete versioned single, threshold, or sequence rule."""

    model_config = ConfigDict(extra="forbid")

    dsl_version: str = DSL_VERSION
    rule_type: Literal["single", "threshold", "sequence"]
    condition: Condition | None = None
    group_by: list[str] = Field(default_factory=list, max_length=8)
    window_seconds: int | None = Field(default=None, gt=0, le=MAX_WINDOW_SECONDS)
    min_count: int | None = Field(default=None, ge=1, le=MAX_PREDICATES)
    distinct_count_field: str | None = None
    stages: list[SequenceStage] = Field(default_factory=list, max_length=MAX_SEQUENCE_STAGES)
    shared_keys: list[str] = Field(default_factory=list, max_length=8)
    max_span_seconds: int | None = Field(default=None, gt=0, le=MAX_WINDOW_SECONDS)

    @model_validator(mode="after")
    def validate_rule_shape(self) -> "DetectionLogic":
        """Require only the fields appropriate for the selected rule type."""
        if self.dsl_version != DSL_VERSION:
            raise ValueError(f"unsupported dsl_version {self.dsl_version!r}; expected {DSL_VERSION!r}")
        keys = set(self.group_by) | set(self.shared_keys)
        invalid_keys = sorted(keys - EVENT_FIELDS)
        if invalid_keys:
            raise ValueError(f"unknown correlation field(s): {', '.join(invalid_keys)}")
        if self.distinct_count_field is not None and self.distinct_count_field not in EVENT_FIELDS:
            raise ValueError(f"unknown distinct_count_field {self.distinct_count_field!r}")
        if self.rule_type == "single":
            if self.condition is None:
                raise ValueError("single rules require condition")
        elif self.rule_type == "threshold":
            if self.condition is None or self.min_count is None or self.window_seconds is None:
                raise ValueError("threshold rules require condition, min_count, and window_seconds")
        else:
            if not self.stages or self.max_span_seconds is None:
                raise ValueError("sequence rules require stages and max_span_seconds")
            if len(self.stages) > MAX_SEQUENCE_STAGES:
                raise ValueError(f"sequence rules may contain at most {MAX_SEQUENCE_STAGES} stages")
        return self


def parse_logic(payload: dict[str, Any] | DetectionLogic) -> DetectionLogic:
    """Validate untrusted JSON into the typed DSL model."""
    if isinstance(payload, DetectionLogic):
        return payload
    return DetectionLogic.model_validate(payload)


__all__ = [
    "Condition", "DetectionLogic", "SequenceStage", "EVENT_FIELDS", "parse_logic",
]
