"""Purpose: Configure the SQLAlchemy engine and session factory for Postgres."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import load_config

settings = load_config()

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for use as a FastAPI dependency.

    Yields:
        An active SQLAlchemy session, closed after the request completes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
