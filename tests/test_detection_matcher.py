from datetime import datetime, timezone

from backend.detection.dsl import Condition
from backend.detection.matcher import match_event


EVENT = {"event_action": "ssh_login", "event_outcome": "failure", "source_port": 22,
         "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc), "source_ip": "192.168.1.5"}


def test_matcher_supports_nested_conditions_and_explanation() -> None:
    condition = Condition(operator="and", children=[
        {"operator": "equals", "field": "event_action", "value": "ssh_login"},
        {"operator": "not", "children": [{"operator": "equals", "field": "event_outcome", "value": "success"}]},
    ])
    result = match_event(EVENT, condition)
    assert result.matched is True
    assert result.explanation.to_dict()["children"][0]["actual"] == "ssh_login"
    assert "event_action equals" in result.explanation.render()


def test_missing_field_semantics_are_explicit() -> None:
    assert not match_event({}, Condition(operator="equals", field="username", value="molly")).matched
    assert not match_event({}, Condition(operator="not_equals", field="username", value="molly")).matched
    assert match_event({}, Condition(operator="not_exists", field="username")).matched
    assert not match_event({}, Condition(operator="not", children=[{"operator": "equals", "field": "username", "value": "molly"}])).matched


def test_time_numeric_cidr_and_type_rules() -> None:
    assert match_event(EVENT, Condition(operator="gte", field="source_port", value=22)).matched
    assert match_event(EVENT, Condition(operator="on_or_after", field="timestamp", value=datetime(2026, 1, 1, tzinfo=timezone.utc))).matched
    assert match_event(EVENT, Condition(operator="cidr_match", field="source_ip", value="192.168.0.0/16")).matched
    assert not match_event(EVENT, Condition(operator="equals", field="source_port", value="22")).matched
