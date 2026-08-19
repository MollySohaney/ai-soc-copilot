"""Purpose: Verify SOC ORM models against an in-memory SQLite database."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
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
