"""Purpose: Provide shared pytest fixtures for API tests.

Testing-only infrastructure: builds an in-memory SQLite database seeded with
the deterministic demo dataset (db.seed.seed) and overrides the app's get_db
dependency to use it, so API tests exercise real endpoint/schema code against
known, reproducible data instead of mocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from backend.security.auth import token_digest
from backend.security.login_limiter import get_login_limiter
from db.base import Base
from db.models import AuthSession, User
from db.seed import seed
from db.session import get_db


TEST_ACCESS_TOKEN = "test-only-bearer-token-not-a-real-secret"


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Provide a Session backed by a fresh in-memory SQLite database seeded with demo data."""
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
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        seed(session)
        test_user = User(
            username="test-analyst",
            password_hash="test-only-password-hash",
            is_active=True,
        )
        session.add(test_user)
        session.flush()
        session.add(
            AuthSession(
                user=test_user,
                token_hash=token_digest(TEST_ACCESS_TOKEN),
                created_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
                last_seen_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
                absolute_expires_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Iterator[TestClient]:
    """Provide a TestClient with get_db overridden to use the seeded in-memory session."""

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app, headers={"Authorization": f"Bearer {TEST_ACCESS_TOKEN}"})
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def anonymous_client(db_session: Session) -> Iterator[TestClient]:
    """Provide an unauthenticated client for login and denial tests."""

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    get_login_limiter().reset()
    try:
        yield TestClient(app)
    finally:
        get_login_limiter().reset()
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def api_client_transport(db_session: Session) -> Iterator[httpx.Client]:
    """Provide an httpx.Client wired straight into the seeded app, no live server.

    Used to exercise api_client/ resource functions (which accept an injectable
    `client: httpx.Client` param) against real endpoint/schema code. httpx's
    ASGITransport only implements the async transport interface in the pinned
    httpx==0.27.2, so it cannot back a sync httpx.Client.request() call; Starlette's
    TestClient solves the same problem by wrapping the ASGI app in a sync-compatible
    transport via an anyio portal, and TestClient is itself an httpx.Client
    subclass, so it satisfies api_client's `httpx.Client` type exactly. The base_url
    includes the `/api/v1` prefix that api_client's resource functions expect the
    client's base_url to already carry.
    """

    def _override_get_db() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    http_client = TestClient(
        app,
        base_url="http://testserver/api/v1",
        headers={"Authorization": f"Bearer {TEST_ACCESS_TOKEN}"},
    )
    try:
        yield http_client
    finally:
        http_client.close()
        app.dependency_overrides.pop(get_db, None)
