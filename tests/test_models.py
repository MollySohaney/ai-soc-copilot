"""Purpose: Verify SOC ORM models against an in-memory SQLite database."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from db.base import Base
from db.models import (
    Alert,
    AlertStatusEnum,
    AIAnalysis,
    Case,
    CaseActivity,
    CaseAlert,
    CasePriorityEnum,
    CaseStatusEnum,
    DetectionRule,
    DetectionRuleVersion,
    DetectionRun,
    Event,
    IngestionCheckpoint,
    IngestionRun,
    SeverityEnum,
)


@pytest.fixture()
def session() -> Iterator[Session]:
    """Provide a Session backed by a fresh in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


def _make_event(event_id: str = "evt-1") -> Event:
    return Event(
        event_id=event_id,
        timestamp=datetime.now(timezone.utc),
        source="edr",
    )


def test_create_and_read_event(session: Session) -> None:
    """An Event row can be created and read back with its fields intact."""
    event = _make_event()
    session.add(event)
    session.commit()

    fetched = session.query(Event).filter_by(event_id="evt-1").one()

    assert fetched.id is not None
    assert fetched.source == "edr"


def test_alert_event_many_to_many(session: Session) -> None:
    """An Alert can be linked to multiple Events, and the link is readable from both sides."""
    event_one = _make_event("evt-1")
    event_two = _make_event("evt-2")
    alert = Alert(
        title="Suspicious login",
        severity=SeverityEnum.HIGH,
        events=[event_one, event_two],
    )
    session.add(alert)
    session.commit()

    fetched_alert = session.query(Alert).filter_by(title="Suspicious login").one()
    assert {e.event_id for e in fetched_alert.events} == {"evt-1", "evt-2"}

    fetched_event = session.query(Event).filter_by(event_id="evt-1").one()
    assert [a.title for a in fetched_event.alerts] == ["Suspicious login"]


def test_case_alert_duplicate_link_rejected(session: Session) -> None:
    """Linking the same alert to the same case twice violates the unique constraint."""
    alert = Alert(title="Malware detected", severity=SeverityEnum.CRITICAL)
    case = Case(case_number="CASE-0001", title="Investigate malware")
    session.add_all([alert, case])
    session.commit()

    session.add(CaseAlert(case_id=case.id, alert_id=alert.id))
    session.commit()

    session.add(CaseAlert(case_id=case.id, alert_id=alert.id))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_create_case_activity(session: Session) -> None:
    """A CaseActivity row can be created against an existing case."""
    case = Case(case_number="CASE-0002", title="Phishing campaign")
    session.add(case)
    session.commit()

    activity = CaseActivity(
        case_id=case.id,
        activity_type="note",
        message="Escalated to tier 2",
        author="analyst@example.com",
    )
    session.add(activity)
    session.commit()

    fetched = session.query(CaseActivity).filter_by(case_id=case.id).one()
    assert fetched.message == "Escalated to tier 2"


def test_create_detection_rule(session: Session) -> None:
    """A DetectionRule row can be created and read back."""
    rule = DetectionRule(
        name="Multiple failed logins",
        query="SELECT * FROM events WHERE event_action = 'login_failed'",
        severity=SeverityEnum.MEDIUM,
    )
    session.add(rule)
    session.commit()

    fetched = session.query(DetectionRule).filter_by(name="Multiple failed logins").one()
    assert fetched.enabled is True
    assert fetched.severity == SeverityEnum.MEDIUM


def test_detection_rule_version_and_run_provenance(session: Session) -> None:
    """Rules, immutable snapshots, runs, and executable alert provenance compose."""
    rule = DetectionRule(
        name="Versioned rule",
        query="legacy query",
        structured_logic={"field": "event_action", "operator": "equals", "value": "login"},
        rule_type="single",
        severity=SeverityEnum.HIGH,
        version=2,
        enabled_for_execution=True,
    )
    session.add(rule)
    session.flush()
    snapshot = DetectionRuleVersion(
        detection_rule_id=rule.id,
        version=rule.version,
        rule_type=rule.rule_type,
        structured_logic=rule.structured_logic,
        legacy_query=rule.query,
    )
    run = DetectionRun(
        detection_rule_id=rule.id,
        rule_version=rule.version,
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
    )
    event = _make_event("evt-versioned")
    alert = Alert(
        title="Versioned alert",
        severity=SeverityEnum.HIGH,
        detection_rule=rule,
        detection_run=run,
        rule_version=rule.version,
        fingerprint="rule-2-firing-1",
        rule_logic_snapshot=rule.structured_logic,
        events=[event],
    )
    session.add_all([snapshot, run, alert])
    session.commit()

    assert rule.versions[0].structured_logic == snapshot.structured_logic
    assert alert.detection_rule_id == rule.id
    assert alert.detection_run.rule_version == 2
    assert alert.events[0].event_id == "evt-versioned"


def test_detection_rule_version_snapshot_is_immutable(session: Session) -> None:
    """Historical rule snapshots cannot be edited after creation."""
    rule = DetectionRule(name="Immutable rule", query="legacy", severity=SeverityEnum.LOW)
    session.add(rule)
    session.flush()
    snapshot = DetectionRuleVersion(
        detection_rule_id=rule.id, version=1, rule_type="single", legacy_query="legacy"
    )
    session.add(snapshot)
    session.commit()
    snapshot.legacy_query = "changed"
    with pytest.raises(ValueError, match="immutable"):
        session.commit()
    session.rollback()


def test_invalid_severity_enum_value_rejected(session: Session) -> None:
    """A severity value outside the enum is rejected when the row is read back."""
    rule = DetectionRule(
        name="Bad severity rule",
        query="SELECT 1",
        severity="not_a_real_severity",
    )
    session.add(rule)
    session.commit()
    session.expunge_all()

    with pytest.raises((StatementError, LookupError, ValueError)):
        session.query(DetectionRule).filter_by(name="Bad severity rule").one()


def test_case_defaults(session: Session) -> None:
    """A Case created without explicit status/priority gets the documented defaults."""
    case = Case(case_number="CASE-0003", title="Default status check")
    session.add(case)
    session.commit()

    fetched = session.query(Case).filter_by(case_number="CASE-0003").one()
    assert fetched.status == CaseStatusEnum.OPEN
    assert fetched.priority == CasePriorityEnum.MEDIUM


def test_alert_default_status(session: Session) -> None:
    """An Alert created without an explicit status gets the documented default."""
    alert = Alert(title="Default status check", severity=SeverityEnum.LOW)
    session.add(alert)
    session.commit()

    fetched = session.query(Alert).filter_by(title="Default status check").one()
    assert fetched.status == AlertStatusEnum.NEW


def test_ai_analysis_persists_alert_scope_and_history(session: Session) -> None:
    """Multiple attempts remain readable in creation order with their provenance."""
    alert = Alert(title="AI scoped alert", severity=SeverityEnum.HIGH)
    session.add(alert)
    session.flush()
    session.add_all(
        [
            AIAnalysis(
                analysis_type="triage",
                alert_id=alert.id,
                provider="fake",
                model="fake-model",
                prompt_version="v1",
                response_schema_version="v1",
                output={"summary": "first"},
                evidence_refs=["event-1"],
                usage={"total_tokens": 12},
                status="succeeded",
            ),
            AIAnalysis(
                analysis_type="triage",
                alert_id=alert.id,
                provider="fake",
                model="fake-model",
                prompt_version="v1",
                response_schema_version="v1",
                output=None,
                evidence_refs=[],
                status="failed",
                error_message="Provider unavailable.",
            ),
        ]
    )
    session.commit()

    records = session.query(AIAnalysis).filter_by(alert_id=alert.id).order_by(AIAnalysis.id).all()
    assert [record.status for record in records] == ["succeeded", "failed"]
    assert records[0].evidence_refs == ["event-1"]
    assert records[0].usage == {"total_tokens": 12}


def test_ai_analysis_requires_alert_or_case_scope(session: Session) -> None:
    """An analysis cannot be persisted without an owning alert or case."""
    from sqlalchemy.exc import IntegrityError

    session.add(
        AIAnalysis(
            analysis_type="triage",
            provider="fake",
            model="fake-model",
            prompt_version="v1",
            response_schema_version="v1",
            status="failed",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()


def test_ai_analysis_records_are_immutable(session: Session) -> None:
    """Updates and deletes cannot rewrite historical analysis attempts."""
    alert = Alert(title="Immutable AI alert", severity=SeverityEnum.LOW)
    session.add(alert)
    session.flush()
    analysis = AIAnalysis(
        analysis_type="triage",
        alert_id=alert.id,
        provider="fake",
        model="fake-model",
        prompt_version="v1",
        response_schema_version="v1",
        status="succeeded",
    )
    session.add(analysis)
    session.commit()

    analysis.status = "failed"
    with pytest.raises(ValueError, match="immutable"):
        session.commit()
    session.rollback()
    session.delete(analysis)
    with pytest.raises(ValueError, match="immutable"):
        session.commit()
    session.rollback()


def test_duplicate_alert_external_id_rejected(session: Session) -> None:
    """Two alerts sharing the same external_id violate the unique constraint."""
    session.add(
        Alert(title="First alert", severity=SeverityEnum.LOW, external_id="ALERT-DUP-001")
    )
    session.commit()

    session.add(
        Alert(title="Second alert", severity=SeverityEnum.LOW, external_id="ALERT-DUP-001")
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_duplicate_event_event_id_rejected(session: Session) -> None:
    """Two events sharing the same event_id violate the unique constraint."""
    session.add(_make_event("evt-dup-1"))
    session.commit()

    session.add(_make_event("evt-dup-1"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_create_ingested_event_with_source_identity(session: Session) -> None:
    """An ingested Event stores source identity, dedup, normalization, and raw evidence."""
    run = IngestionRun(provider="elastic", source_name="elastic-default")
    event = Event(
        event_id="evt-ingested-1",
        dedup_key="elastic:logs-security:abc123",
        ingestion_run=run,
        timestamp=datetime.now(timezone.utc),
        source="elastic",
        source_provider="elastic",
        source_instance="elastic-default",
        source_index="logs-security",
        source_record_id="abc123",
        event_category="authentication",
        normalization_version="ecs-v1",
        normalization_warnings=["missing user.name"],
        raw_payload={"_id": "abc123", "_source": {"event": {"category": "authentication"}}},
    )
    session.add(event)
    session.commit()

    fetched = session.query(Event).filter_by(event_id="evt-ingested-1").one()

    assert fetched.ingestion_run.provider == "elastic"
    assert fetched.dedup_key == "elastic:logs-security:abc123"
    assert fetched.source_provider == "elastic"
    assert fetched.source_instance == "elastic-default"
    assert fetched.source_index == "logs-security"
    assert fetched.source_record_id == "abc123"
    assert fetched.normalization_version == "ecs-v1"
    assert fetched.normalization_warnings == ["missing user.name"]
    assert fetched.raw_payload == {
        "_id": "abc123",
        "_source": {"event": {"category": "authentication"}},
    }


def test_duplicate_event_dedup_key_rejected(session: Session) -> None:
    """Two ingested events sharing the same dedup_key violate the unique constraint."""
    session.add(
        Event(
            event_id="evt-dedup-1",
            dedup_key="elastic:logs-security:dup",
            timestamp=datetime.now(timezone.utc),
            source="elastic",
        )
    )
    session.commit()

    session.add(
        Event(
            event_id="evt-dedup-2",
            dedup_key="elastic:logs-security:dup",
            timestamp=datetime.now(timezone.utc),
            source="elastic",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_create_ingestion_checkpoint(session: Session) -> None:
    """An IngestionCheckpoint stores restart state for one provider source."""
    run = IngestionRun(
        provider="elastic",
        source_name="elastic-default",
        status="succeeded",
        fetched_count=2,
        persisted_count=2,
    )
    checkpoint = IngestionCheckpoint(
        provider="elastic",
        source_name="elastic-default",
        checkpoint={"search_after": ["2026-08-15T02:00:00Z", "abc123"]},
        last_run=run,
    )
    session.add(checkpoint)
    session.commit()

    fetched = session.query(IngestionCheckpoint).filter_by(provider="elastic").one()

    assert fetched.source_name == "elastic-default"
    assert fetched.checkpoint == {"search_after": ["2026-08-15T02:00:00Z", "abc123"]}
    assert fetched.last_run.status == "succeeded"


def test_duplicate_ingestion_checkpoint_source_rejected(session: Session) -> None:
    """A provider/source pair has exactly one checkpoint row."""
    session.add(
        IngestionCheckpoint(
            provider="elastic",
            source_name="elastic-default",
            checkpoint={"search_after": ["a"]},
        )
    )
    session.commit()

    session.add(
        IngestionCheckpoint(
            provider="elastic",
            source_name="elastic-default",
            checkpoint={"search_after": ["b"]},
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_duplicate_detection_rule_name_rejected_at_db_layer(session: Session) -> None:
    """Two detection rules sharing the same name violate the unique constraint, at the DB layer directly."""
    session.add(
        DetectionRule(
            name="Duplicate rule name",
            query="SELECT 1",
            severity=SeverityEnum.LOW,
        )
    )
    session.commit()

    session.add(
        DetectionRule(
            name="Duplicate rule name",
            query="SELECT 2",
            severity=SeverityEnum.HIGH,
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_case_activity_nonexistent_case_id_rejected(session: Session) -> None:
    """A CaseActivity referencing a nonexistent case_id violates the foreign key constraint."""
    session.add(
        CaseActivity(
            case_id=99999,
            activity_type="note",
            message="Orphaned activity",
            author="analyst@example.com",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
