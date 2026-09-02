from datetime import datetime, timedelta, timezone

from backend.detection.dsl import DetectionLogic
from backend.detection.sequence import evaluate_sequence


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(event_id: str, seconds: int, action: str, user: str = "molly") -> dict:
    return {"event_id": event_id, "timestamp": BASE + timedelta(seconds=seconds),
            "event_action": action, "hostname": "host-1", "username": user}


def rule(span: int = 60) -> DetectionLogic:
    return DetectionLogic(
        rule_type="sequence", shared_keys=["hostname", "username"], max_span_seconds=span,
        stages=[
            {"label": "failed", "condition": {"operator": "equals", "field": "event_action", "value": "failed"}},
            {"label": "success", "condition": {"operator": "equals", "field": "event_action", "value": "success"}},
            {"label": "persist", "condition": {"operator": "equals", "field": "event_action", "value": "persist"}},
        ],
    )


def test_sequence_returns_ordered_stage_evidence_and_ignores_interleaving() -> None:
    result = evaluate_sequence([event("s", 20, "success"), event("f", 0, "failed"),
                                event("noise", 10, "noise"), event("p", 30, "persist")], rule())
    assert len(result) == 1
    assert result[0].stage_evidence == {"failed": ("f",), "success": ("s",), "persist": ("p",)}
    assert result[0].span == timedelta(seconds=30)


def test_sequence_rejects_reordering_mismatched_keys_and_span() -> None:
    assert evaluate_sequence([event("p", 0, "persist"), event("f", 1, "failed"), event("s", 2, "success")], rule()) == []
    assert evaluate_sequence([event("f", 0, "failed"), event("s", 1, "success", "other"), event("p", 2, "persist")], rule()) == []
    assert evaluate_sequence([event("f", 0, "failed"), event("s", 1, "success"), event("p", 61, "persist")], rule(60)) == []


def test_sequence_requires_all_stages_and_shared_keys() -> None:
    assert evaluate_sequence([event("f", 0, "failed"), event("s", 1, "success")], rule()) == []
    missing = [event("f", 0, "failed"), event("s", 1, "success"), event("p", 2, "persist")]
    missing[0]["username"] = None
    assert evaluate_sequence(missing, rule()) == []
