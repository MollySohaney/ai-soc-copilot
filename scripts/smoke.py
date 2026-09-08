"""Purpose: Verify in one command that the local demo stack is actually working.

Each check is a small pure function over an injected session or HTTP client so the
whole set can be exercised in tests without a live server. Credentials are read from
the process environment only; no password is ever accepted as a command-line argument,
printed, or logged.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass

import httpx
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from db.models import Alert, DetectionRule

SEED_SENTINEL_ALERT = "ALERT-0005"


@dataclass(frozen=True)
class CheckResult:
    """Record the outcome of one smoke check."""

    name: str
    ok: bool
    detail: str


def alembic_head_revision(ini_path: str = "alembic.ini") -> str:
    """Return the head revision Alembic would upgrade to.

    Args:
        ini_path: Path to the Alembic configuration file.

    Returns:
        The head revision identifier, or an empty string if none is defined.
    """
    script = ScriptDirectory.from_config(Config(ini_path))
    return script.get_current_head() or ""


def applied_revision(db: Session) -> str | None:
    """Return the revision recorded in the database, or None if unmigrated.

    Args:
        db: Database session.

    Returns:
        The applied revision identifier, or None when no version table exists.
    """
    try:
        return db.scalar(text("select version_num from alembic_version"))
    except Exception:  # noqa: BLE001 - an unmigrated database raises driver-specific errors
        db.rollback()
        return None


def check_database(db: Session) -> CheckResult:
    """Verify the database accepts a trivial query."""
    try:
        db.execute(text("select 1"))
    except Exception as error:  # noqa: BLE001
        return CheckResult(
            "database",
            False,
            f"Cannot reach PostgreSQL. Start it with `docker compose up -d`. ({type(error).__name__})",
        )
    return CheckResult("database", True, "Reachable.")


def check_migrations(db: Session, head: str) -> CheckResult:
    """Verify the database schema is at the Alembic head revision."""
    current = applied_revision(db)
    if current is None:
        return CheckResult(
            "migrations",
            False,
            "No schema applied. Run `alembic upgrade head`.",
        )
    if current != head:
        return CheckResult(
            "migrations",
            False,
            f"Schema is at {current}, head is {head}. Run `alembic upgrade head`.",
        )
    return CheckResult("migrations", True, f"At head ({head}).")


def check_seed_data(db: Session) -> CheckResult:
    """Verify the deterministic demo dataset is present."""
    try:
        sentinel = db.scalar(select(Alert).where(Alert.external_id == SEED_SENTINEL_ALERT))
        rule_count = db.scalar(select(func.count()).select_from(DetectionRule)) or 0
    except Exception as error:  # noqa: BLE001
        return CheckResult("seed_data", False, f"Cannot query demo data. ({type(error).__name__})")
    if sentinel is None:
        return CheckResult(
            "seed_data",
            False,
            f"{SEED_SENTINEL_ALERT} is missing. Run `python -m db.seed`.",
        )
    if rule_count == 0:
        return CheckResult("seed_data", False, "No detection rules. Run `python -m db.seed`.")
    return CheckResult("seed_data", True, f"{SEED_SENTINEL_ALERT} present, {rule_count} rules.")


def check_api_health(client: httpx.Client) -> CheckResult:
    """Verify the API process answers its liveness route."""
    try:
        response = client.get("/api/v1/health")
    except httpx.HTTPError as error:
        return CheckResult(
            "api_health",
            False,
            f"No response. Start it with `uvicorn api.main:app --port 8000`. ({type(error).__name__})",
        )
    if response.status_code != 200:
        return CheckResult("api_health", False, f"Returned HTTP {response.status_code}.")
    return CheckResult("api_health", True, "Liveness OK.")


def check_api_ready(client: httpx.Client) -> CheckResult:
    """Verify the API can reach its database dependency."""
    try:
        response = client.get("/api/v1/ready")
    except httpx.HTTPError as error:
        return CheckResult("api_ready", False, f"No response. ({type(error).__name__})")
    if response.status_code != 200:
        return CheckResult(
            "api_ready",
            False,
            f"Returned HTTP {response.status_code}. The API cannot reach PostgreSQL.",
        )
    return CheckResult("api_ready", True, "Readiness OK.")


def check_authenticated_read(
    client: httpx.Client, *, username: str, password: str | None
) -> CheckResult:
    """Verify a demo account can log in and read alerts."""
    if not password:
        return CheckResult(
            "authenticated_read",
            False,
            "DEMO_PASSWORD is not set in the environment, so login was not attempted.",
        )
    try:
        login = client.post(
            "/api/v1/auth/login", json={"username": username, "password": password}
        )
    except httpx.HTTPError as error:
        return CheckResult("authenticated_read", False, f"No response. ({type(error).__name__})")
    if login.status_code != 200:
        return CheckResult(
            "authenticated_read",
            False,
            f"Login for '{username}' returned HTTP {login.status_code}. "
            "Run `python -m db.bootstrap_user` and check DEMO_PASSWORD.",
        )
    token = login.json().get("access_token", "")
    alerts = client.get(
        "/api/v1/alerts", headers={"Authorization": f"Bearer {token}"}, params={"page_size": 1}
    )
    if alerts.status_code != 200:
        return CheckResult(
            "authenticated_read",
            False,
            f"Authenticated alert read returned HTTP {alerts.status_code}.",
        )
    return CheckResult("authenticated_read", True, f"'{username}' can read alerts.")


def run_checks(
    db: Session,
    client: httpx.Client,
    *,
    head: str,
    username: str,
    password: str | None,
) -> list[CheckResult]:
    """Run every smoke check in dependency order.

    Args:
        db: Database session.
        client: HTTP client pointed at the API base URL.
        head: Expected Alembic head revision.
        username: Demo account to authenticate as.
        password: Demo account password from the environment, or None.

    Returns:
        One result per check, in the order they were run.
    """
    database = check_database(db)
    if not database.ok:
        return [database]
    migrations = check_migrations(db, head)
    results = [database, migrations]
    if migrations.ok:
        results.append(check_seed_data(db))
    health = check_api_health(client)
    results.append(health)
    if not health.ok:
        return results
    results.append(check_api_ready(client))
    results.append(check_authenticated_read(client, username=username, password=password))
    return results


def format_report(results: Sequence[CheckResult]) -> str:
    """Render check results as aligned terminal output."""
    width = max((len(result.name) for result in results), default=0)
    lines = [
        f"{'PASS' if result.ok else 'FAIL'}  {result.name.ljust(width)}  {result.detail}"
        for result in results
    ]
    failed = [result for result in results if not result.ok]
    lines.append("")
    lines.append(
        "All checks passed."
        if not failed
        else f"{len(failed)} of {len(results)} checks failed."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the smoke checks against the configured local stack."""
    import argparse

    from config.settings import load_config
    from db.session import SessionLocal

    parser = argparse.ArgumentParser(
        description="Check that the local AI SOC Copilot demo stack is working."
    )
    parser.add_argument(
        "--username",
        default=os.getenv("DEMO_USERNAME", "demo-admin"),
        help="Demo account to authenticate as (or set DEMO_USERNAME).",
    )
    args = parser.parse_args(argv)

    config = load_config()
    password = os.getenv("DEMO_PASSWORD")
    with SessionLocal() as db, httpx.Client(base_url=config.api_base_url, timeout=10.0) as client:
        results = run_checks(
            db,
            client,
            head=alembic_head_revision(),
            username=args.username,
            password=password,
        )
    print(format_report(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
