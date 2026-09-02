"""Tests for the bounded, data-only detection DSL."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.detection.dsl import Condition, DetectionLogic, parse_logic


def test_all_leaf_operators_validate() -> None:
    """Each supported leaf operator accepts its documented value shape."""
    values = {
        "equals": "ssh_login", "not_equals": "other", "contains": "ssh",
        "not_contains": "http", "starts_with": "ssh", "ends_with": "login",
        "in": ["ssh_login", "sudo"], "not_in": ["http"], "gt": 2,
        "gte": 2, "lt": 9, "lte": 9, "cidr_match": "192.168.0.0/16",
        "before": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "after": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "on_or_before": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "on_or_after": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    for operator, value in values.items():
        assert Condition(operator=operator, field="event_action", value=value).operator == operator
    assert Condition(operator="exists", field="event_action").value is None
    assert Condition(operator="not_exists", field="event_action").value is None


@pytest.mark.parametrize(
    "payload",
    [
        {"operator": "regex", "field": "message", "value": ".*"},
        {"operator": "equals", "field": "__class__", "value": "x"},
        {"operator": "equals", "field": "raw_payload.secret", "value": "x"},
        {"operator": "equals", "field": "message"},
        {"operator": "gt", "field": "message", "value": "5"},
        {"operator": "before", "field": "timestamp", "value": "2026-01-01"},
        {"operator": "in", "field": "message", "value": []},
        {"operator": "exists", "field": "message", "value": True},
    ],
)
def test_invalid_leaf_payloads_are_rejected(payload: dict) -> None:
    """Unknown fields/operators and ambiguous values fail at the boundary."""
    with pytest.raises(ValidationError):
        Condition.model_validate(payload)


def test_boolean_groups_and_round_trip_are_stable() -> None:
    """Nested boolean data serializes and validates losslessly."""
    logic = DetectionLogic(
        rule_type="single",
        condition={
            "operator": "and",
            "children": [
                {"operator": "equals", "field": "event_outcome", "value": "failure"},
                {"operator": "not", "children": [
                    {"operator": "equals", "field": "username", "value": "root"},
                ]},
            ],
        },
    )
    assert parse_logic(logic.model_dump(mode="json")) == logic
    assert logic.model_dump(mode="json") == parse_logic(logic.model_dump(mode="json")).model_dump(mode="json")


def test_threshold_and_sequence_limits_are_enforced() -> None:
    """Correlation structures require bounded windows and stage counts."""
    with pytest.raises(ValidationError):
        DetectionLogic(rule_type="threshold", condition={"operator": "exists", "field": "hostname"}, min_count=2)
    with pytest.raises(ValidationError):
        DetectionLogic(
            rule_type="sequence",
            max_span_seconds=86_401,
            stages=[{"condition": {"operator": "exists", "field": "hostname"}}],
        )
