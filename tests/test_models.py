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
    Case,
    CaseActivity,
    CaseAlert,
    CasePriorityEnum,
    CaseStatusEnum,
    DetectionRule,
    Event,
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
