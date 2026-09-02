from datetime import datetime, timedelta, timezone

import pytest

from db.models import Alert, DetectionRule, Event, SeverityEnum, DetectionRun
from db.models.alert import alert_event
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


def test_failed_execution_is_recorded(monkeypatch, db_session) -> None:
    """Evaluator failures leave a finalized failed DetectionRun with detail."""
    rule = DetectionRule(
        name="Failing threshold", query="legacy", severity=SeverityEnum.MEDIUM,
        enabled_for_execution=True,
        structured_logic={"rule_type": "threshold", "condition": {"operator": "exists", "field": "event_action"}, "group_by": [], "window_seconds": 60, "min_count": 1},
    )
    db_session.add(rule)
    db_session.flush()
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic evaluator failure")
    monkeypatch.setattr("backend.detection.service.evaluate_threshold", fail)
    from datetime import datetime, timezone
    with pytest.raises(RuntimeError, match="synthetic"):
        execute_rule(db_session, rule, window_start=datetime(2026, 1, 1, tzinfo=timezone.utc), window_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc))
    run = db_session.query(DetectionRun).filter_by(detection_rule_id=rule.id).one()
    assert run.status == "failed"
    assert run.error_detail == "synthetic evaluator failure"


def test_sequence_alert_persists_stage_labels_and_explanation(db_session) -> None:
    """A sequence alert retains labeled evidence provenance for analysts."""
    from db.seed import BASE_TIME
    rule = db_session.query(DetectionRule).filter(DetectionRule.rule_type == "sequence").order_by(DetectionRule.id.desc()).first()
    assert rule is not None
    result = execute_rule(db_session, rule, window_start=BASE_TIME, window_end=BASE_TIME + timedelta(hours=1))
    assert result.alerts_created
    alert_id = result.alerts_created[0]
    alert = db_session.get(Alert, alert_id)
    assert alert is not None and alert.match_explanation["stages"]
    labels = {row.stage for row in db_session.execute(alert_event.select().where(alert_event.c.alert_id == alert_id))}
    assert {"failed", "success", "privilege_escalation", "persistence"}.issubset(labels)


def test_seeded_critical_alerts_never_use_only_benign_noise(db_session) -> None:
    """The benign fixture population does not produce an unexpected critical alert."""
    from db.seed import BASE_TIME
    rules = db_session.query(DetectionRule).all()
    results = [execute_rule(db_session, rule, window_start=BASE_TIME, window_end=BASE_TIME + timedelta(hours=1)) for rule in rules]
    generated_ids = [alert_id for result in results for alert_id in result.alerts_created]
    noise_ids = {event.event_id for event in db_session.query(Event).filter(Event.dataset == "noise")}
    for alert in db_session.query(Alert).filter(Alert.id.in_(generated_ids), Alert.severity == SeverityEnum.CRITICAL):
        linked_ids = {event.event_id for event in alert.events}
        assert linked_ids and not linked_ids.issubset(noise_ids)
