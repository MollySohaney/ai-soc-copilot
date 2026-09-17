from __future__ import annotations

import uuid

import pytest

from db.reset_demo import reset_demo


def test_reset_demo_requires_matching_confirmation(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "demo")
    with pytest.raises(RuntimeError, match="matching"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="wrong")


def test_reset_demo_refuses_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(RuntimeError, match="outside"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="ai_soc_copilot_demo")


def test_reset_demo_falls_back_to_app_env(monkeypatch):
    """APP_ENV is honored when ENVIRONMENT is unset, so one setting governs both."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError, match="outside"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="ai_soc_copilot_demo")


def test_environment_takes_precedence_over_app_env(monkeypatch):
    """An explicit ENVIRONMENT still wins, preserving the existing contract."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("APP_ENV", "development")
    with pytest.raises(RuntimeError, match="outside"):
        reset_demo(database_name="ai_soc_copilot_demo", confirmation="ai_soc_copilot_demo")


def _postgres_session():
    """Return a session bound to the configured PostgreSQL database, or None.

    The append-only trigger is created only on PostgreSQL (alembic revision
    d8b4f9e1a623), so the SQLite fixtures used by the rest of the suite cannot
    reach this bug at all. CI provides a migrated PostgreSQL 16 service.
    """
    from sqlalchemy import inspect

    from db.session import SessionLocal, engine

    if engine.dialect.name != "postgresql":
        return None
    try:
        if "audit_events" not in inspect(engine).get_table_names():
            return None
    except Exception:  # pragma: no cover - unreachable database
        return None
    return SessionLocal()


def test_delete_all_rows_clears_the_append_only_audit_table():
    """The reset must clear audit_events despite its append-only trigger.

    A plain DELETE raises 'audit_events is append-only' and aborts the whole
    reset. Everything here runs inside a transaction that is rolled back, so a
    developer's local database is never emptied by the test.
    """
    session = _postgres_session()
    if session is None:
        pytest.skip("requires a migrated PostgreSQL database")

    from sqlalchemy import func, select

    from db.models import AuditEvent
    from db.reset_demo import _append_only_trigger_present, _delete_all_rows

    try:
        if not _append_only_trigger_present(session):
            pytest.skip("append-only trigger is not installed on this database")

        session.add(
            AuditEvent(
                event_id=str(uuid.uuid4()),
                actor_type="system",
                action="test.reset",
                outcome="succeeded",
            )
        )
        session.flush()
        assert session.scalar(select(func.count()).select_from(AuditEvent)) > 0

        _delete_all_rows(session)

        assert session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    finally:
        session.rollback()
        session.close()


def test_append_only_trigger_is_restored_after_a_rolled_back_reset():
    """Disabling the trigger must not outlive the reset transaction."""
    session = _postgres_session()
    if session is None:
        pytest.skip("requires a migrated PostgreSQL database")

    from sqlalchemy import text

    from db.reset_demo import _append_only_trigger_present, _delete_all_rows

    try:
        if not _append_only_trigger_present(session):
            pytest.skip("append-only trigger is not installed on this database")
        _delete_all_rows(session)
    finally:
        session.rollback()
        session.close()

    verify = _postgres_session()
    try:
        assert _append_only_trigger_present(verify)
        verify.execute(text("INSERT INTO audit_events (event_id, actor_type, action, outcome, occurred_at)"
                            " VALUES ('trigger-check-row', 'system', 'test.trigger', 'succeeded', now())"))
        verify.flush()
        with pytest.raises(Exception, match="append-only"):
            verify.execute(text("DELETE FROM audit_events WHERE event_id = 'trigger-check-row'"))
    finally:
        verify.rollback()
        verify.close()
