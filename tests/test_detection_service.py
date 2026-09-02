from datetime import datetime, timedelta, timezone

from db.models import DetectionRule, Event, SeverityEnum, DetectionRun
from backend.detection.service import execute_rule


def test_execution_service_creates_idempotent_alerts(db_session) -> None:
    rule = DetectionRule(name="Executable", query="legacy", severity=SeverityEnum.HIGH,
                         enabled_for_execution=True, structured_logic={"rule_type": "single", "condition": {"operator": "equals", "field": "event_action", "value": "signal"}}, version=1)
    event = Event(event_id="service-event", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), source="fixture", event_action="signal")
    db_session.add_all([rule, event]); db_session.flush()
    result = execute_rule(db_session, rule, window_start=datetime(2026, 1, 1, tzinfo=timezone.utc), window_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc))
    assert result.alerts_created
    second = execute_rule(db_session, rule, window_start=datetime(2026, 1, 1, tzinfo=timezone.utc), window_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc))
    assert second.alerts_created == ()


def test_dry_run_does_not_persist_run_or_alert(db_session) -> None:
    rule = DetectionRule(name="Dry run", query="legacy", severity=SeverityEnum.LOW,
                         enabled_for_execution=True, structured_logic={"rule_type": "single", "condition": {"operator": "exists", "field": "event_action"}})
    event = Event(event_id="dry-event", timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), source="fixture", event_action="signal")
    existing_rules = db_session.query(DetectionRule).count()
    existing_runs = db_session.query(DetectionRun).count()
    db_session.add_all([rule, event]); db_session.flush()
    result = execute_rule(db_session, rule, window_start=datetime(2026, 1, 1, tzinfo=timezone.utc), window_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc), dry_run=True)
    assert result.status == "dry_run" and result.would_fire
    assert db_session.query(DetectionRule).count() == existing_rules + 1
    assert db_session.query(DetectionRun).count() == existing_runs
