"""Purpose: Verify the demo smoke helper passes on a healthy stack and fails loudly."""

from __future__ import annotations

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.security.auth import create_user
from db.base import Base
from db.models import RoleEnum
from scripts.smoke import (
    CheckResult,
    alembic_head_revision,
    applied_revision,
    check_api_health,
    check_api_ready,
    check_authenticated_read,
    check_database,
    check_migrations,
    check_seed_data,
    format_report,
    run_checks,
)

HEAD = "0123456789ab"
PASSWORD = "correct-horse-battery-staple"


@pytest.fixture()
def empty_session() -> Iterator[Session]:
    """Provide a schema-only session with no demo data, standing in for an unseeded database."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _stamp_revision(db: Session, revision: str) -> None:
    db.execute(text("create table alembic_version (version_num varchar(32) not null)"))
    db.execute(text("insert into alembic_version (version_num) values (:v)"), {"v": revision})
    db.commit()


def _unreachable_client() -> httpx.Client:
    def _raise(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.Client(transport=httpx.MockTransport(_raise), base_url="http://localhost:8000")


class _UnreachableSession:
    """Stand in for a session whose database is not accepting connections."""

    def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("select 1", {}, Exception("connection refused"))

    def scalar(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("select 1", {}, Exception("connection refused"))

    def rollback(self) -> None:
        return None


class TestDatabaseChecks:
    """Cover the checks that run before the API is contacted."""

    def test_database_check_passes_against_a_live_session(self, db_session: Session) -> None:
        """A reachable database reports success."""
        assert check_database(db_session).ok

    def test_unmigrated_database_names_the_fix(self, empty_session: Session) -> None:
        """A database with no version table tells the reader to run migrations."""
        result = check_migrations(empty_session, HEAD)
        assert not result.ok
        assert "alembic upgrade head" in result.detail

    def test_stale_revision_reports_both_revisions(self, empty_session: Session) -> None:
        """A schema behind head names the applied revision and the head."""
        _stamp_revision(empty_session, "old-revision")
        result = check_migrations(empty_session, HEAD)
        assert not result.ok
        assert "old-revision" in result.detail
        assert HEAD in result.detail

    def test_schema_at_head_passes(self, empty_session: Session) -> None:
        """A schema stamped at head passes."""
        _stamp_revision(empty_session, HEAD)
        assert check_migrations(empty_session, HEAD).ok

    def test_applied_revision_is_none_without_a_version_table(
        self, empty_session: Session
    ) -> None:
        """The revision reader recovers from the missing-table error."""
        assert applied_revision(empty_session) is None
        assert check_database(empty_session).ok

    def test_seed_data_check_passes_on_the_demo_dataset(self, db_session: Session) -> None:
        """The seeded sentinel alert and rules are both found."""
        result = check_seed_data(db_session)
        assert result.ok
        assert "ALERT-0005" in result.detail

    def test_missing_seed_data_names_the_fix(self, empty_session: Session) -> None:
        """An empty database tells the reader to run the seed command."""
        result = check_seed_data(empty_session)
        assert not result.ok
        assert "python -m db.seed" in result.detail

    def test_head_revision_resolves_from_the_migration_directory(self) -> None:
        """The helper reads a real head revision out of alembic/."""
        assert alembic_head_revision()


class TestApiChecks:
    """Cover the checks that require a running API process."""

    def test_health_and_readiness_pass_against_the_app(
        self, anonymous_client: TestClient
    ) -> None:
        """Both API checks succeed when the service and its database are up."""
        assert check_api_health(anonymous_client).ok
        assert check_api_ready(anonymous_client).ok

    def test_missing_api_names_the_start_command(self) -> None:
        """A refused connection tells the reader how to start the API."""
        with _unreachable_client() as client:
            result = check_api_health(client)
        assert not result.ok
        assert "uvicorn api.main:app" in result.detail

    def test_readiness_failure_points_at_postgres(self) -> None:
        """A 503 readiness response blames the database dependency."""
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(503)),
            base_url="http://localhost:8000",
        ) as client:
            result = check_api_ready(client)
        assert not result.ok
        assert "PostgreSQL" in result.detail


class TestAuthenticatedRead:
    """Cover the end-to-end login and read check."""

    def test_missing_password_is_reported_not_guessed(
        self, anonymous_client: TestClient
    ) -> None:
        """No password in the environment is a clear failure, not a silent skip."""
        result = check_authenticated_read(anonymous_client, username="demo-admin", password=None)
        assert not result.ok
        assert "DEMO_PASSWORD" in result.detail

    def test_valid_credentials_read_alerts(
        self, db_session: Session, anonymous_client: TestClient
    ) -> None:
        """A real account logs in and reads alerts through the API."""
        create_user(db_session, username="demo-admin", password=PASSWORD, role=RoleEnum.ADMIN)
        db_session.commit()
        result = check_authenticated_read(
            anonymous_client, username="demo-admin", password=PASSWORD
        )
        assert result.ok

    def test_wrong_credentials_name_the_bootstrap_command(
        self, anonymous_client: TestClient
    ) -> None:
        """A failed login tells the reader to bootstrap the account."""
        result = check_authenticated_read(
            anonymous_client, username="nobody", password="wrong-password"
        )
        assert not result.ok
        assert "db.bootstrap_user" in result.detail

    def test_no_password_appears_in_any_check_detail(
        self, db_session: Session, anonymous_client: TestClient
    ) -> None:
        """Check output never echoes the credential it was given."""
        create_user(db_session, username="demo-admin", password=PASSWORD, role=RoleEnum.ADMIN)
        db_session.commit()
        results = run_checks(
            db_session,
            anonymous_client,
            head=HEAD,
            username="demo-admin",
            password=PASSWORD,
        )
        assert PASSWORD not in format_report(results)


class TestOrchestration:
    """Cover ordering, short-circuiting, and the exit contract."""

    def test_unreachable_database_short_circuits_every_later_check(
        self, anonymous_client: TestClient
    ) -> None:
        """Nothing else is attempted once the database is gone."""
        results = run_checks(
            _UnreachableSession(),
            anonymous_client,
            head=HEAD,
            username="demo-admin",
            password=PASSWORD,
        )
        assert [result.name for result in results] == ["database"]
        assert "docker compose up -d" in results[0].detail

    def test_unreachable_api_short_circuits_readiness_and_login(
        self, db_session: Session
    ) -> None:
        """A dead API stops the run before readiness and authentication."""
        with _unreachable_client() as client:
            results = run_checks(
                db_session, client, head=HEAD, username="demo-admin", password=PASSWORD
            )
        names = [result.name for result in results]
        assert names[-1] == "api_health"
        assert "api_ready" not in names
        assert "authenticated_read" not in names

    def test_report_counts_failures(self) -> None:
        """The summary line states how many checks failed."""
        report = format_report(
            [CheckResult("a", True, "fine"), CheckResult("b", False, "broken")]
        )
        assert "FAIL  b" in report
        assert "1 of 2 checks failed." in report

    def test_report_confirms_a_fully_healthy_stack(self) -> None:
        """A clean run says so plainly."""
        assert "All checks passed." in format_report([CheckResult("a", True, "fine")])
