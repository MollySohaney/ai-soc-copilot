"""Purpose: Provide shared pytest fixtures for API tests.

Testing-only infrastructure: builds an in-memory SQLite database seeded with
the deterministic demo dataset (db.seed.seed) and overrides the app's get_db
dependency to use it, so API tests exercise real endpoint/schema code against
known, reproducible data instead of mocks.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import app
from db.base import Base
from db.seed import seed
from db.session import get_db


@pytest.fixture()
def db_session() -> Iterator[Session]:
    """Provide a Session backed by a fresh in-memory SQLite database seeded with demo data."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_factory()
    try:
        seed(session)
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
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
