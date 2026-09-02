from datetime import datetime, timedelta, timezone

from backend.detection.dsl import DetectionLogic
from backend.detection.threshold import evaluate_threshold


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(event_id: str, seconds: int, source_ip: str | None = "192.168.1.5") -> dict:
    return {"event_id": event_id, "timestamp": BASE + timedelta(seconds=seconds),
            "event_action": "ssh_login", "source_ip": source_ip, "hostname": "host-1"}


def logic(min_count: int = 2) -> DetectionLogic:
    return DetectionLogic(rule_type="threshold", group_by=["source_ip"], window_seconds=60,
                          min_count=min_count,
                          condition={"operator": "equals", "field": "event_action", "value": "ssh_login"})


def test_threshold_exact_boundary_and_group_evidence() -> None:
    result = evaluate_threshold([event("e2", 10), event("e1", 0), event("end", 60)], logic(), BASE, BASE + timedelta(seconds=120))
    assert len(result) == 1
    assert result[0].count == 2
    assert result[0].evidence_event_ids == ("e1", "e2")
    assert result[0].window_start == BASE


def test_threshold_does_not_combine_groups_or_missing_keys() -> None:
    events = [event("a", 1, "1.1.1.1"), event("b", 2, "2.2.2.2"), event("c", 3, None)]
    assert evaluate_threshold(events, logic(), BASE, BASE + timedelta(seconds=60)) == []


def test_threshold_distinct_count() -> None:
    rule = DetectionLogic(rule_type="threshold", group_by=["source_ip"], window_seconds=60,
                          min_count=2, distinct_count_field="hostname",
                          condition={"operator": "exists", "field": "event_action"})
    events = [event("a", 1), event("b", 2), event("c", 3)]
    events[1]["hostname"] = "host-2"
    assert evaluate_threshold(events, rule, BASE, BASE + timedelta(seconds=60))[0].count == 2
