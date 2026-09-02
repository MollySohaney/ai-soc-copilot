"""Phase 4 deterministic execution and bounded-safety regression gate."""

from datetime import timedelta

import pytest

from backend.detection.service import execute_rule
from db.models import DetectionRule
from db.seed import BASE_TIME


def test_seeded_rules_fire_and_overlap_rerun_is_idempotent(db_session) -> None:
    """Every executable seeded rule can run twice without duplicate alerts."""
    rules = db_session.query(DetectionRule).order_by(DetectionRule.id).all()
    first = [
        execute_rule(db_session, rule, window_start=BASE_TIME, window_end=BASE_TIME + timedelta(hours=1))
        for rule in rules
    ]
    assert all(result.status == "completed" for result in first)
    assert sum(len(result.alerts_created) for result in first) > 0
    second = [
        execute_rule(db_session, rule, window_start=BASE_TIME + timedelta(minutes=30), window_end=BASE_TIME + timedelta(hours=1))
        for rule in rules
    ]
    assert all(result.alerts_created == () for result in second)


def test_execution_rejects_oversized_window(db_session) -> None:
    rule = db_session.query(DetectionRule).first()
    assert rule is not None
    with pytest.raises(ValueError, match="lookback"):
        execute_rule(db_session, rule, window_start=BASE_TIME - timedelta(seconds=1), window_end=BASE_TIME + timedelta(hours=2))


def test_execution_surfaces_scan_cap(db_session) -> None:
    rule = db_session.query(DetectionRule).first()
    assert rule is not None
    rule.max_events_scanned = 1
    result = execute_rule(db_session, rule, window_start=BASE_TIME, window_end=BASE_TIME + timedelta(hours=1), dry_run=True)
    assert result.truncated is True
    assert result.events_scanned == 1
