"""Safely reset a disposable local/demo database and reseed deterministic data."""
from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from db.models import Base
from db.seed import seed
from db.session import SessionLocal, engine

# `audit_events` is protected by a row-level BEFORE UPDATE OR DELETE trigger
# (see alembic revision d8b4f9e1a623). A plain DELETE therefore aborts the whole
# reset on PostgreSQL. The trigger is the real append-only guarantee, so the
# reset lifts it explicitly and only for the duration of its own transaction
# rather than working around it.
AUDIT_TABLE = "audit_events"
AUDIT_APPEND_ONLY_TRIGGER = "audit_events_append_only"


def _append_only_trigger_present(session: Session) -> bool:
    """Return whether the append-only trigger exists on this connection."""
    if session.bind is None or session.bind.dialect.name != "postgresql":
        return False
    return bool(
        session.scalar(
            text(
                "select 1 from pg_trigger"
                " where tgname = :name and not tgisinternal"
            ),
            {"name": AUDIT_APPEND_ONLY_TRIGGER},
        )
    )


def _delete_all_rows(session: Session) -> None:
    """Delete every application row, including the append-only audit table.

    The audit trigger is disabled and re-enabled inside the caller's
    transaction. PostgreSQL DDL is transactional, so an error anywhere in the
    reset rolls the trigger back into place along with the deletes; the table
    is never left unprotected.
    """
    guarded = _append_only_trigger_present(session)
    if guarded:
        session.execute(
            text(f"ALTER TABLE {AUDIT_TABLE} DISABLE TRIGGER {AUDIT_APPEND_ONLY_TRIGGER}")
        )
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())
    if guarded:
        session.execute(
            text(f"ALTER TABLE {AUDIT_TABLE} ENABLE TRIGGER {AUDIT_APPEND_ONLY_TRIGGER}")
        )


def reset_demo(*, database_name: str, confirmation: str) -> None:
    """Delete all application rows only after explicit environment confirmation."""
    environment = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "development").lower()
    if environment not in {"development", "demo", "test", "local"}:
        raise RuntimeError("Refusing reset outside a local/demo environment.")
    if confirmation != database_name:
        raise RuntimeError("Reset requires --confirm-database matching the connected database.")
    with engine.connect() as connection:
        actual = connection.scalar(text("select current_database()"))
    if actual != database_name:
        raise RuntimeError("Reset requires --confirm-database matching the connected database.")
    with SessionLocal.begin() as session:
        _delete_all_rows(session)
        seed(session)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reset and reseed a disposable SOC demo database.")
    parser.add_argument("--database-name", default=os.getenv("POSTGRES_DB", "ai_soc_copilot"))
    parser.add_argument("--confirm-database", required=True)
    args = parser.parse_args(argv)
    reset_demo(database_name=args.database_name, confirmation=args.confirm_database)
    print(f"Reset and reseeded disposable database '{args.database_name}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
