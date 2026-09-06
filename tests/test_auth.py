"""Purpose: Verify local credentials, bearer sessions, expiry, and revocation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.main import app
from backend.security.auth import (
    create_user,
    hash_password,
    revoke_user_sessions,
    token_digest,
    verify_password,
)
from config.settings import AppConfig, load_config
from db.bootstrap_user import bootstrap_user
from db.models import AuthSession, User


def _create_login_user(db: Session, username: str = "local-analyst") -> tuple[User, str]:
    password = "correct-horse-battery-staple"
    user, created = create_user(db, username=username, password=password)
    assert created
    db.commit()
    return user, password


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()


def test_passwords_use_salted_argon2id_hashes() -> None:
    """Password hashes are adaptive, salted, and never contain plaintext."""
    password = "a-long-test-only-password"
    first = hash_password(password)
    second = hash_password(password)

    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert first != second
    assert password not in first
    assert verify_password(first, password)
    assert not verify_password(first, "wrong-test-password")


def test_login_returns_token_once_and_persists_only_digest(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """A successful login exposes no password hash and stores no raw token."""
    user, password = _create_login_user(db_session)
    body = _login(anonymous_client, user.username, password)

    assert body["token_type"] == "bearer"
    assert body["user"] == {
        "id": user.id,
        "username": user.username,
        "role": "viewer",
        "is_active": True,
    }
    assert "password" not in str(body).lower()
    session = db_session.scalar(
        select(AuthSession).where(AuthSession.user_id == user.id)
    )
    assert session is not None
    assert session.token_hash == token_digest(body["access_token"])
    assert body["access_token"] not in session.token_hash


def test_invalid_username_and_password_share_generic_failure(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """Login failures do not disclose whether a local username exists."""
    user, _ = _create_login_user(db_session)

    wrong_password = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "wrong-test-password"},
    )
    missing_user = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": "missing-user", "password": "wrong-test-password"},
    )

    assert wrong_password.status_code == missing_user.status_code == 401
    assert wrong_password.json()["error"]["message"] == "Invalid username or password."
    assert missing_user.json()["error"]["message"] == "Invalid username or password."

    oversized_secret = "secret-canary-" + ("x" * 1100)
    oversized = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": oversized_secret},
    )
    assert oversized.status_code == 422
    assert oversized_secret not in oversized.text


def test_anonymous_users_can_reach_health_but_not_protected_data(
    anonymous_client: TestClient,
) -> None:
    """The shared API dependency protects every non-auth business router."""
    assert anonymous_client.get("/api/v1/health").status_code == 200
    response = anonymous_client.get("/api/v1/alerts")
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Authentication required."
    assert response.headers["www-authenticate"] == "Bearer"


def test_every_non_public_api_operation_requires_authentication(
    anonymous_client: TestClient,
) -> None:
    """Route additions cannot accidentally bypass the shared protected router."""
    public_operations = {
        ("GET", "/api/v1/health"),
        ("GET", "/api/v1/ready"),
        ("POST", "/api/v1/auth/login"),
    }
    checked: set[tuple[str, str]] = set()
    for route in app.routes:
        if not route.path.startswith("/api/v1"):
            continue
        path = re.sub(r"\{[^}]+\}", "1", route.path)
        for method in route.methods or set():
            operation = (method, route.path)
            if method in {"HEAD", "OPTIONS"} or operation in public_operations:
                continue
            response = anonymous_client.request(method, path, json={})
            assert response.status_code == 401, operation
            checked.add(operation)

    assert checked


def test_session_idle_expiry_revokes_token(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """A session cannot be used after its configured idle window."""
    user, password = _create_login_user(db_session)
    body = _login(anonymous_client, user.username, password)
    session = db_session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(body["access_token"]))
    )
    assert session is not None
    session.last_seen_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()

    response = anonymous_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert response.status_code == 401
    db_session.refresh(session)
    assert session.revoked_at is not None


def test_session_absolute_expiry_revokes_token(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """Recent activity cannot extend a session beyond its absolute lifetime."""
    user, password = _create_login_user(db_session)
    body = _login(anonymous_client, user.username, password)
    session = db_session.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(body["access_token"]))
    )
    assert session is not None
    session.absolute_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()

    response = anonymous_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert response.status_code == 401


def test_logout_revokes_current_session(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """Logout is idempotent from the user's perspective and invalidates reuse."""
    user, password = _create_login_user(db_session)
    body = _login(anonymous_client, user.username, password)
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    assert anonymous_client.get("/api/v1/auth/me", headers=headers).status_code == 200
    assert anonymous_client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert anonymous_client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_disabled_user_and_explicit_revocation_invalidate_all_sessions(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """Disabling or centrally revoking a user blocks existing bearer sessions."""
    user, password = _create_login_user(db_session)
    first = _login(anonymous_client, user.username, password)
    second = _login(anonymous_client, user.username, password)
    revoke_user_sessions(db_session, user_id=user.id)

    for body in (first, second):
        response = anonymous_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {body['access_token']}"},
        )
        assert response.status_code == 401

    active_before_disable = _login(anonymous_client, user.username, password)
    user.is_active = False
    db_session.commit()
    disabled_session = anonymous_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {active_before_disable['access_token']}"},
    )
    assert disabled_session.status_code == 401
    disabled_login = anonymous_client.post(
        "/api/v1/auth/login", json={"username": user.username, "password": password}
    )
    assert disabled_login.status_code == 401


def test_failed_logins_are_bounded(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """The login boundary applies a configurable per-client/user failure limit."""
    user, password = _create_login_user(db_session)
    config = AppConfig(auth_login_max_attempts=2, auth_login_window_seconds=60)
    app.dependency_overrides[load_config] = lambda: config
    try:
        for _ in range(2):
            response = anonymous_client.post(
                "/api/v1/auth/login",
                json={"username": user.username, "password": "wrong-test-password"},
            )
            assert response.status_code == 401
        blocked = anonymous_client.post(
            "/api/v1/auth/login", json={"username": user.username, "password": password}
        )
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
    finally:
        app.dependency_overrides.pop(load_config, None)


def test_successful_login_clears_prior_failures(
    anonymous_client: TestClient, db_session: Session
) -> None:
    """One valid login resets the per-client/user failure window."""
    user, password = _create_login_user(db_session)
    config = AppConfig(auth_login_max_attempts=2, auth_login_window_seconds=60)
    app.dependency_overrides[load_config] = lambda: config
    try:
        failed = anonymous_client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "wrong-test-password"},
        )
        assert failed.status_code == 401
        assert _login(anonymous_client, user.username, password)["access_token"]
        for _ in range(2):
            failed = anonymous_client.post(
                "/api/v1/auth/login",
                json={"username": user.username, "password": "wrong-test-password"},
            )
            assert failed.status_code == 401
    finally:
        app.dependency_overrides.pop(load_config, None)


def test_demo_bootstrap_is_idempotent_and_does_not_replace_password(
    db_session: Session,
) -> None:
    """Re-running explicit bootstrap leaves an existing credential unchanged."""
    first, created = bootstrap_user(
        db_session, username="demo-viewer", password="first-test-only-password"
    )
    original_hash = first.password_hash
    second, created_again = bootstrap_user(
        db_session, username="DEMO-viewer", password="second-test-only-password"
    )

    assert created
    assert not created_again
    assert first.id == second.id
    assert second.password_hash == original_hash
    assert verify_password(second.password_hash, "first-test-only-password")
    assert not verify_password(second.password_hash, "second-test-only-password")
