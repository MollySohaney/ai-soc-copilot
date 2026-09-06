"""Safely reset a disposable local/demo database and reseed deterministic data."""
from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from sqlalchemy import text

from db.models import Base
from db.seed import seed
from db.session import SessionLocal, engine


def reset_demo(*, database_name: str, confirmation: str) -> None:
    """Delete all application rows only after explicit environment confirmation."""
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment not in {"development", "demo", "test", "local"}:
        raise RuntimeError("Refusing reset outside a local/demo environment.")
    if confirmation != database_name:
        raise RuntimeError("Reset requires --confirm-database matching the connected database.")
    with engine.connect() as connection:
        actual = connection.scalar(text("select current_database()"))
    if actual != database_name:
        raise RuntimeError("Reset requires --confirm-database matching the connected database.")
    with SessionLocal.begin() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
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
