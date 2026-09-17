"""Purpose: Verify db.seed.seed() produces a deterministic, idempotent SOC demo dataset."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from db.base import Base
from db.models import Alert, Case, CaseAlert, DetectionRule, Event
from db.models.alert import alert_event
from db.seed import seed
from backend.detection.dsl import parse_logic


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


def _counts(session: Session) -> dict[str, int]:
    return {
        "events": session.query(Event).count(),
        "alerts": session.query(Alert).count(),
        "rules": session.query(DetectionRule).count(),
        "cases": session.query(Case).count(),
    }


def test_seed_creates_expected_row_counts_and_chain(session: Session) -> None:
    """A single seed run lands row counts in the required ranges and forms a full chain."""
    seed(session)
    session.commit()

    counts = _counts(session)
    assert 50 <= counts["events"] <= 100
    assert 10 <= counts["alerts"] <= 15
    assert 3 <= counts["rules"] <= 5
    assert 2 <= counts["cases"] <= 3

    chain_alert = session.query(Alert).filter_by(external_id="ALERT-0001").one()
    linked_events = session.execute(
        alert_event.select().where(alert_event.c.alert_id == chain_alert.id)
    ).fetchall()
    assert len(linked_events) > 1

    case_alert = (
        session.query(CaseAlert).filter_by(alert_id=chain_alert.id).one_or_none()
    )
    assert case_alert is not None
    assert session.query(Case).filter_by(id=case_alert.case_id).one() is not None


def test_seed_is_idempotent_on_rerun(session: Session) -> None:
    """Running seed() twice against the same session produces no duplicate rows."""
    seed(session)
    session.commit()
    first_counts = _counts(session)

    seed(session)
    session.commit()
    second_counts = _counts(session)

    assert second_counts == first_counts


def test_seed_rerun_preserves_deterministic_values(session: Session) -> None:
    """A known deterministic value on the correlated chain alert survives re-seeding unchanged."""
    seed(session)
    session.commit()

    chain_alert_before = session.query(Alert).filter_by(external_id="ALERT-0006").one()
    external_id_before = chain_alert_before.external_id
    created_at_before = chain_alert_before.created_at

    seed(session)
    session.commit()

    chain_alert_after = session.query(Alert).filter_by(external_id="ALERT-0006").one()
    assert chain_alert_after.external_id == external_id_before
    assert chain_alert_after.created_at == created_at_before


def test_seeded_detection_pack_contains_valid_structured_logic(session: Session) -> None:
    """Every seeded rule is executable data validated by the Phase 4 DSL."""
    seed(session)
    session.commit()
    rules = session.query(DetectionRule).all()
    assert len(rules) == 5
    assert all(rule.structured_logic for rule in rules)
    assert {parse_logic(rule.structured_logic).rule_type for rule in rules} == {
        "single", "threshold", "sequence"
    }


def test_reseeding_repairs_rules_that_drifted_from_the_spec(session: Session) -> None:
    """Re-seeding restores rule configuration that an older schema left behind.

    `get_or_create` applies defaults on insert only, so a rule row created
    before `enabled_for_execution` existed kept the column default of False.
    Every such rule then reported "skipped" instead of executing, and the demo
    pipeline printed that as an OK step.
    """
    seed(session)
    session.flush()

    rule = session.query(DetectionRule).filter_by(name="SSH Brute Force Detection").one()
    original_id = rule.id
    rule.enabled_for_execution = False
    rule.structured_logic = {"dsl_version": "1", "rule_type": "single",
                             "condition": {"operator": "exists", "field": "event_action"}}
    rule.risk_score = 1
    session.flush()

    seed(session)
    session.flush()

    restored = session.query(DetectionRule).filter_by(name="SSH Brute Force Detection").one()
    assert restored.id == original_id, "re-seeding must repair the row, not insert a duplicate"
    assert restored.enabled_for_execution is True
    assert restored.structured_logic["rule_type"] == "threshold"
    assert restored.risk_score == 55


def test_reseeding_preserves_analyst_state_on_alerts_and_cases(session: Session) -> None:
    """Convergence is scoped to configuration; analyst decisions are not clobbered."""
    seed(session)
    session.flush()

    alert = session.query(Alert).order_by(Alert.id).first()
    case = session.query(Case).order_by(Case.id).first()
    alert.status = "closed"
    case.status = "resolved"
    session.flush()

    seed(session)
    session.flush()

    assert session.get(Alert, alert.id).status == "closed"
    assert session.get(Case, case.id).status == "resolved"


def test_every_seeded_rule_is_enabled_for_execution(session: Session) -> None:
    """The demo pipeline is only meaningful if the seeded pack actually executes."""
    seed(session)
    session.flush()

    rules = session.query(DetectionRule).all()
    assert rules
    assert all(rule.enabled_for_execution for rule in rules)
