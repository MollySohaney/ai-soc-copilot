"""Purpose: Provide local password and opaque-session authentication services."""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from config.settings import AppConfig
from db.models import AuthSession, RoleEnum, User

_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65_536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,
)
_DUMMY_PASSWORD_HASH = _PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


class AuthenticationError(Exception):
    """Represent an invalid or expired authentication attempt."""


@dataclass(frozen=True)
class IssuedSession:
    """Return a raw token exactly once alongside its persisted session metadata."""

    access_token: str
    session: AuthSession


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Bind the authenticated user to the session that proved the identity."""

    user: User
    session: AuthSession


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize timestamps returned without timezone data by SQLite tests."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_username(username: str) -> str:
    """Normalize and validate a local username."""
    normalized = username.strip().lower()
    if not _USERNAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "Username must be 3-64 lowercase letters, numbers, dots, underscores, or hyphens."
        )
    return normalized


def validate_password(password: str) -> None:
    """Apply safe local credential bounds before invoking Argon2."""
    encoded_length = len(password.encode("utf-8"))
    if encoded_length < 12:
        raise ValueError("Password must be at least 12 bytes long.")
    if encoded_length > 1024:
        raise ValueError("Password must not exceed 1024 bytes.")


def hash_password(password: str) -> str:
    """Hash a validated password with Argon2id and a per-password salt."""
    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password without allowing malformed hashes to escape."""
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    role: RoleEnum = RoleEnum.VIEWER,
) -> tuple[User, bool]:
    """Create a local user once without changing an existing credential."""
    normalized = normalize_username(username)
    existing = db.scalar(select(User).where(User.username == normalized))
    if existing is not None:
        return existing, False

    user = User(
        username=normalized,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user, True


def authenticate_user(db: Session, *, username: str, password: str) -> User | None:
    """Authenticate without exposing whether a username exists through timing."""
    if len(password.encode("utf-8")) > 1024:
        password = "password-input-exceeded-safe-bound"
        password_within_bounds = False
    else:
        password_within_bounds = True
    try:
        normalized = normalize_username(username)
    except ValueError:
        normalized = ""
    user = db.scalar(select(User).where(User.username == normalized))
    candidate_hash = user.password_hash if user is not None else _DUMMY_PASSWORD_HASH
    valid = verify_password(candidate_hash, password)
    if user is None or not user.is_active or not valid or not password_within_bounds:
        return None

    if _PASSWORD_HASHER.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = utc_now()
    return user


def token_digest(access_token: str) -> str:
    """Derive the database lookup value for a raw opaque session token."""
    return hashlib.sha256(access_token.encode("utf-8")).hexdigest()


def issue_session(db: Session, *, user: User, config: AppConfig) -> IssuedSession:
    """Issue a high-entropy token while persisting only its digest."""
    now = utc_now()
    access_token = secrets.token_urlsafe(32)
    session = AuthSession(
        user=user,
        token_hash=token_digest(access_token),
        created_at=now,
        last_seen_at=now,
        absolute_expires_at=now + timedelta(hours=config.auth_session_absolute_hours),
    )
    db.add(session)
    db.flush()
    return IssuedSession(access_token=access_token, session=session)


def authenticate_session(
    db: Session, *, access_token: str, config: AppConfig, now: datetime | None = None
) -> AuthenticatedPrincipal:
    """Validate revocation, user status, idle expiry, and absolute expiry."""
    if len(access_token) > 512:
        raise AuthenticationError("Authentication required.")
    current_time = now or utc_now()
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(access_token))
    )
    if session is None or session.revoked_at is not None or not session.user.is_active:
        raise AuthenticationError("Authentication required.")

    idle_expires_at = _as_utc(session.last_seen_at) + timedelta(
        minutes=config.auth_session_idle_minutes
    )
    if current_time >= _as_utc(session.absolute_expires_at) or current_time >= idle_expires_at:
        session.revoked_at = current_time
        db.commit()
        raise AuthenticationError("Authentication required.")

    session.last_seen_at = current_time
    db.commit()
    return AuthenticatedPrincipal(user=session.user, session=session)


def revoke_session(db: Session, *, session: AuthSession) -> None:
    """Revoke one session idempotently."""
    if session.revoked_at is None:
        session.revoked_at = utc_now()
        db.commit()


def revoke_user_sessions(db: Session, *, user_id: int) -> None:
    """Revoke all live sessions for a disabled or credential-reset user."""
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
    db.commit()
