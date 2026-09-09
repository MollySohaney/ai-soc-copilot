"""Purpose: Verify the demo pipeline drives fixture ingestion and detection over the API."""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.security.auth import create_user
from db.models import Event, RoleEnum
from scripts.demo_pipeline import (
    DEMO_DETECT_END,
    DEMO_DETECT_START,
    DEMO_INGEST_END,
    DEMO_INGEST_START,
    DemoPipelineError,
    StepResult,
    execute_rules,
    format_report,
    ingest_fixture_telemetry,
    list_rules,
    login,
    run_pipeline,
)

PASSWORD = "correct-horse-battery-staple"


def _account(db: Session, *, username: str, role: RoleEnum) -> str:
    create_user(db, username=username, password=PASSWORD, role=role)
    db.commit()
    return username


def _token(client: TestClient, username: str) -> str:
    return login(client, username=username, password=PASSWORD)


@pytest.fixture()
def admin_token(db_session: Session, anonymous_client: TestClient) -> str:
    """Provide a bearer token for an account holding every demo permission."""
    return _token(anonymous_client, _account(db_session, username="demo-admin", role=RoleEnum.ADMIN))


class TestLogin:
    """Cover authentication, which every other step depends on."""

    def test_valid_credentials_return_a_token(self, admin_token: str) -> None:
        """A successful login yields a non-empty opaque token."""
        assert admin_token

    def test_bad_credentials_raise_with_a_next_action(
        self, anonymous_client: TestClient
    ) -> None:
        """A rejected login says what the reader should do about it."""
        with pytest.raises(DemoPipelineError, match="DEMO_PASSWORD"):
            login(anonymous_client, username="nobody", password="wrong-password")


class TestFixtureIngestion:
    """Cover the fixture telemetry path, which must not need Elastic."""

    def test_ingestion_persists_events_without_elastic(
        self, db_session: Session, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """Fixture records land in the events table with no external service."""
        before = db_session.scalar(select(func.count()).select_from(Event)) or 0
        result = ingest_fixture_telemetry(anonymous_client, token=admin_token)
        assert result.ok, result.detail
        after = db_session.scalar(select(func.count()).select_from(Event)) or 0
        assert after > before

    def test_second_run_is_idempotent(
        self, db_session: Session, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """Re-running ingestion writes no additional events."""
        ingest_fixture_telemetry(anonymous_client, token=admin_token)
        after_first = db_session.scalar(select(func.count()).select_from(Event)) or 0
        result = ingest_fixture_telemetry(anonymous_client, token=admin_token)
        assert result.ok, result.detail
        assert (db_session.scalar(select(func.count()).select_from(Event)) or 0) == after_first

    def test_empty_window_persists_nothing(
        self, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """A window with no fixture records still succeeds and reports zero."""
        result = ingest_fixture_telemetry(
            anonymous_client,
            token=admin_token,
            start=DEMO_INGEST_START - timedelta(days=10),
            end=DEMO_INGEST_START - timedelta(days=9),
        )
        assert result.ok
        assert "persisted=0" in result.detail

    def test_analyst_is_denied_and_told_which_permission_is_missing(
        self, db_session: Session, anonymous_client: TestClient
    ) -> None:
        """Ingestion is Admin-only, and the denial names the permission."""
        token = _token(
            anonymous_client, _account(db_session, username="demo-analyst", role=RoleEnum.ANALYST)
        )
        result = ingest_fixture_telemetry(anonymous_client, token=token)
        assert not result.ok
        assert "operate_integrations" in result.detail


class TestDetectionExecution:
    """Cover deterministic rule execution over the seeded window."""

    def test_seeded_rules_are_listed(
        self, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """The demo dataset exposes rules for the pipeline to execute."""
        assert list_rules(anonymous_client, token=admin_token)

    def test_enabled_rules_execute_and_scan_events(
        self, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """Every executed rule reports a scan rather than an error."""
        rules = list_rules(anonymous_client, token=admin_token)
        results = execute_rules(anonymous_client, token=admin_token, rules=rules)
        assert results
        assert all(result.ok for result in results), [r.detail for r in results if not r.ok]

    def test_rules_not_enabled_for_execution_are_skipped_not_failed(
        self, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """A disabled rule is reported as skipped, keeping the run green."""
        results = execute_rules(
            anonymous_client,
            token=admin_token,
            rules=[{"id": 1, "name": "disabled-rule", "enabled_for_execution": False}],
        )
        assert results[0].ok
        assert "Skipped" in results[0].detail

    def test_analyst_is_denied_and_told_which_permission_is_missing(
        self, db_session: Session, anonymous_client: TestClient, admin_token: str
    ) -> None:
        """Rule execution is denied to an Analyst, naming manage_detections."""
        rules = list_rules(anonymous_client, token=admin_token)
        analyst = _token(
            anonymous_client, _account(db_session, username="demo-analyst", role=RoleEnum.ANALYST)
        )
        results = execute_rules(anonymous_client, token=analyst, rules=rules[:1])
        assert not results[0].ok
        assert "manage_detections" in results[0].detail

    def test_detection_window_fits_inside_every_seeded_rule_lookback(self) -> None:
        """The window covers the 02:00-02:09 chain without exceeding a 3600s lookback."""
        assert DEMO_DETECT_END - DEMO_DETECT_START == timedelta(seconds=3600)
        chain_start = DEMO_INGEST_START + timedelta(hours=2)
        assert DEMO_DETECT_START <= chain_start
        assert DEMO_DETECT_END >= chain_start + timedelta(minutes=9)

    def test_ingestion_window_stays_inside_the_api_query_cap(self) -> None:
        """The ingestion window is well under the 31-day maximum."""
        assert DEMO_INGEST_START < DEMO_INGEST_END
        assert (DEMO_INGEST_END - DEMO_INGEST_START) <= timedelta(days=31)


class TestPipeline:
    """Cover the whole pipeline and its reporting."""

    def test_full_pipeline_runs_ingestion_then_detection(
        self, db_session: Session, anonymous_client: TestClient
    ) -> None:
        """One call logs in, ingests, and executes every enabled rule."""
        _account(db_session, username="demo-admin", role=RoleEnum.ADMIN)
        results = run_pipeline(anonymous_client, username="demo-admin", password=PASSWORD)
        assert results[0].name == "fixture_ingestion"
        assert len(results) > 1
        assert all(result.ok for result in results), [r.detail for r in results if not r.ok]

    def test_report_never_echoes_the_password(
        self, db_session: Session, anonymous_client: TestClient
    ) -> None:
        """Pipeline output contains no credential material."""
        _account(db_session, username="demo-admin", role=RoleEnum.ADMIN)
        results = run_pipeline(anonymous_client, username="demo-admin", password=PASSWORD)
        assert PASSWORD not in format_report(results)

    def test_report_counts_failed_steps(self) -> None:
        """The summary line states how many steps failed."""
        report = format_report([StepResult("a", True, "ok"), StepResult("b", False, "denied")])
        assert "FAIL  b" in report
        assert "1 of 2 steps failed." in report


def test_unreachable_api_surfaces_a_transport_error() -> None:
    """A refused connection raises rather than reporting a false success."""

    def _raise(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with httpx.Client(
        transport=httpx.MockTransport(_raise), base_url="http://localhost:8000"
    ) as client:
        with pytest.raises(httpx.ConnectError):
            login(client, username="demo-admin", password=PASSWORD)
