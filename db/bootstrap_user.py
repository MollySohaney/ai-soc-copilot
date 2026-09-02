"""Purpose: Safely bootstrap one local demo user from explicit operator input."""

from __future__ import annotations

import argparse
import getpass
import os
import secrets
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.security.auth import create_user, normalize_username
from db.models import RoleEnum, User
from db.session import SessionLocal


def bootstrap_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: RoleEnum = RoleEnum.ANALYST,
) -> tuple[User, bool]:
    """Create a user idempotently and commit only the new record."""
    user, created = create_user(db, username=username, password=password, role=role)
    db.commit()
    return user, created


def _password_from_operator(*, generate: bool) -> tuple[str, bool]:
    configured = os.getenv("DEMO_PASSWORD")
    if configured:
        return configured, False
    if generate:
        return secrets.token_urlsafe(24), True
    password = getpass.getpass("Demo user password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise ValueError("Passwords do not match.")
    return password, False


def main(argv: Sequence[str] | None = None) -> int:
    """Run the explicit local demo-user bootstrap command."""
    parser = argparse.ArgumentParser(description="Create one local AI SOC Copilot demo user.")
    parser.add_argument(
        "--username",
        default=os.getenv("DEMO_USERNAME", "demo-analyst"),
        help="Local username (or set DEMO_USERNAME).",
    )
    parser.add_argument(
        "--role",
        choices=[role.value for role in RoleEnum],
        default=RoleEnum.ANALYST.value,
        help="Initial least-privilege role (default: analyst for the demo workflow).",
    )
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="Generate and print a password once when DEMO_PASSWORD is unset.",
    )
    args = parser.parse_args(argv)
    username = normalize_username(args.username)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == username))
        if existing is not None:
            print(f"Demo user '{username}' already exists; credentials were not changed.")
            return 0

        password, generated = _password_from_operator(generate=args.generate_password)
        user, created = bootstrap_user(
            db, username=username, password=password, role=RoleEnum(args.role)
        )
        if not created:
            print(f"Demo user '{user.username}' already exists; credentials were not changed.")
            return 0
        print(f"Created demo user '{user.username}'.")
        if generated:
            print("Generated password (shown once; store it securely):")
            print(password)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
