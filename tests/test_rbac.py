"""Purpose: Prove the server-side role matrix for every sensitive API operation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.main import app
from backend.security.auth import token_digest
from backend.security.rbac import (
    ROLE_PERMISSIONS,
    AuthorizationDenied,
    Permission,
    require_user_permission,
    role_has_permission,
)
from backend.services.user_admin_service import FinalAdminError, UserAdminService
from db.models import AuthSession, RoleEnum, User
from db.session import get_db


@dataclass(frozen=True)
class SensitiveOperation:
    """Describe one permission-bearing API operation."""

    method: str
    path: str
    payload: dict[str, Any] | None
    permission: Permission


RULE_PAYLOAD = {
    "name": "RBAC matrix rule",
    "description": "Created only by an authorized role.",
    "source": "custom",
    "language": "sigma",
    "query": "event_category:test",
    "severity": "medium",
    "risk_score": 50,
    "enabled": True,
}

SENSITIVE_OPERATIONS = (
    SensitiveOperation("PATCH", "/api/v1/alerts/99999", {"status": "in_progress"}, Permission.MUTATE_INVESTIGATIONS),
    SensitiveOperation("POST", "/api/v1/cases", {"title": "RBAC matrix case"}, Permission.MUTATE_INVESTIGATIONS),
    SensitiveOperation("PATCH", "/api/v1/cases/99999", {"status": "in_progress"}, Permission.MUTATE_INVESTIGATIONS),
    SensitiveOperation("POST", "/api/v1/cases/99999/alerts", {"alert_ids": [1]}, Permission.MUTATE_INVESTIGATIONS),
    SensitiveOperation("DELETE", "/api/v1/cases/99999/alerts/1", None, Permission.MUTATE_INVESTIGATIONS),
    SensitiveOperation("POST", "/api/v1/cases/99999/activities", {"activity_type": "note", "message": "RBAC test"}, Permission.MUTATE_INVESTIGATIONS),
    SensitiveOperation("POST", "/api/v1/alerts/99999/ai/triage", {}, Permission.REQUEST_AI),
    SensitiveOperation("POST", "/api/v1/cases/99999/ai/ask", {"question": "What happened?"}, Permission.REQUEST_AI),
    SensitiveOperation("POST", "/api/v1/cases/99999/ai/report", {}, Permission.REQUEST_AI),
    SensitiveOperation("POST", "/api/v1/rules/validate", {"logic": {"rule_type": "single", "condition": {"operator": "exists", "field": "hostname"}}}, Permission.MANAGE_DETECTIONS),
    SensitiveOperation("POST", "/api/v1/rules/test", {"rule_id": 1}, Permission.MANAGE_DETECTIONS),
    SensitiveOperation("POST", "/api/v1/rules/execute", {"rule_id": 1}, Permission.MANAGE_DETECTIONS),
    SensitiveOperation("POST", "/api/v1/rules", RULE_PAYLOAD, Permission.MANAGE_DETECTIONS),
    SensitiveOperation("PATCH", "/api/v1/rules/99999", {"enabled": False}, Permission.MANAGE_DETECTIONS),
    SensitiveOperation("POST", "/api/v1/ingestion/fixture/test", {}, Permission.OPERATE_INTEGRATIONS),
    SensitiveOperation("POST", "/api/v1/ingestion/fixture/sync", {"start_time": "2026-08-15T02:00:00Z", "end_time": "2026-08-15T03:00:00Z", "limit": 10, "dry_run": True}, Permission.OPERATE_INTEGRATIONS),
    SensitiveOperation("GET", "/api/v1/ingestion/status", None, Permission.OPERATE_INTEGRATIONS),
    SensitiveOperation("GET", "/api/v1/ingestion/runs", None, Permission.OPERATE_INTEGRATIONS),
    SensitiveOperation("GET", "/api/v1/admin/users", None, Permission.MANAGE_USERS),
    SensitiveOperation("POST", "/api/v1/admin/users", {"username": "rbac-created", "password": "rbac-test-only-password", "role": "viewer"}, Permission.MANAGE_USERS),
    SensitiveOperation("PATCH", "/api/v1/admin/users/99999", {"role": "viewer"}, Permission.MANAGE_USERS),
    SensitiveOperation("POST", "/api/v1/admin/users/99999/revoke-sessions", {}, Permission.MANAGE_USERS),
    SensitiveOperation("GET", "/api/v1/audit-events", None, Permission.READ_AUDIT),
)


def _role_client(db: Session, role: RoleEnum) -> TestClient:
    token = f"test-only-{role.value}-bearer-token"
    user = User(
        username=f"rbac-{role.value.replace('_', '-')}",
        password_hash="test-only-password-hash",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        AuthSession(
            user=user,
            token_hash=token_digest(token),
            created_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            last_seen_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            absolute_expires_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()
    return TestClient(app, headers={"Authorization": f"Bearer {token}"})


def test_permission_matrix_has_exact_least_privilege_grants() -> None:
    """The single source of truth matches the documented four-role matrix."""
    assert ROLE_PERMISSIONS == {
        RoleEnum.VIEWER: frozenset({Permission.READ_SOC}),
        RoleEnum.ANALYST: frozenset(
            {Permission.READ_SOC, Permission.MUTATE_INVESTIGATIONS, Permission.REQUEST_AI}
        ),
        RoleEnum.DETECTION_ENGINEER: frozenset(
            {Permission.READ_SOC, Permission.MANAGE_DETECTIONS}
        ),
        RoleEnum.ADMIN: frozenset(Permission),
    }


def test_every_sensitive_endpoint_allows_and_denies_each_role(
    db_session: Session,
) -> None:
    """Every sensitive route checks its declared permission before target lookup."""

    def _override_get_db():  # noqa: ANN202
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        for role in RoleEnum:
            with _role_client(db_session, role) as client:
                for operation in SENSITIVE_OPERATIONS:
                    response = client.request(
                        operation.method,
                        operation.path,
                        json=operation.payload,
                    )
                    if role_has_permission(role, operation.permission):
                        assert response.status_code not in {401, 403}, (
                            role,
                            operation,
                            response.text,
                        )
                    else:
                        assert response.status_code == 403, (
                            role,
                            operation,
                            response.text,
                        )
                        assert response.json()["error"]["message"] == "Insufficient permission."
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_service_layer_rejects_non_admin_direct_call(db_session: Session) -> None:
    """Direct user-service invocation cannot bypass the permission matrix."""
    viewer = User(
        username="direct-viewer",
        password_hash="test-only-password-hash",
        role=RoleEnum.VIEWER,
        is_active=True,
    )
    db_session.add(viewer)
    db_session.commit()

    with pytest.raises(AuthorizationDenied, match="Insufficient permission"):
        UserAdminService(db_session).list_users(actor=viewer, page=1, page_size=20)
    with pytest.raises(AuthorizationDenied, match="Insufficient permission"):
        require_user_permission(viewer, Permission.READ_AUDIT)


def test_final_active_admin_cannot_be_demoted_or_disabled(db_session: Session) -> None:
    """Administrative changes preserve at least one active Admin."""
    admin = db_session.scalar(select(User).where(User.role == RoleEnum.ADMIN))
    assert admin is not None
    service = UserAdminService(db_session)

    with pytest.raises(FinalAdminError):
        service.update_user(
            actor=admin,
            user_id=admin.id,
            role=RoleEnum.VIEWER,
            is_active=None,
        )
    with pytest.raises(FinalAdminError):
        service.update_user(
            actor=admin,
            user_id=admin.id,
            role=None,
            is_active=False,
        )


def test_role_change_revokes_target_sessions(db_session: Session) -> None:
    """Changing authorization invalidates already-issued bearer sessions."""
    admin = db_session.scalar(select(User).where(User.role == RoleEnum.ADMIN))
    assert admin is not None
    analyst = User(
        username="role-change-analyst",
        password_hash="test-only-password-hash",
        role=RoleEnum.ANALYST,
        is_active=True,
    )
    db_session.add(analyst)
    db_session.flush()
    session = AuthSession(
        user=analyst,
        token_hash=token_digest("test-only-role-change-token"),
        created_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        absolute_expires_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(session)
    db_session.commit()

    updated = UserAdminService(db_session).update_user(
        actor=admin,
        user_id=analyst.id,
        role=RoleEnum.VIEWER,
        is_active=None,
    )
    db_session.refresh(session)
    assert updated.role == RoleEnum.VIEWER
    assert session.revoked_at is not None


def test_admin_api_manages_only_safe_user_fields(
    client: TestClient, db_session: Session
) -> None:
    """Admin user creation and role changes never expose the password hash."""
    created = client.post(
        "/api/v1/admin/users",
        json={
            "username": "managed-user",
            "password": "managed-test-only-password",
            "role": "viewer",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["role"] == "viewer"
    assert "password" not in created.text.lower()

    session = AuthSession(
        user_id=body["id"],
        token_hash=token_digest("test-only-managed-user-token"),
        created_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
        absolute_expires_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(session)
    db_session.commit()
    updated = client.patch(
        f"/api/v1/admin/users/{body['id']}", json={"role": "analyst"}
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "analyst"
    db_session.refresh(session)
    assert session.revoked_at is not None


def test_admin_api_protects_final_active_admin(
    client: TestClient, db_session: Session
) -> None:
    """The HTTP boundary preserves the final-Admin service invariant."""
    admin = db_session.scalar(select(User).where(User.role == RoleEnum.ADMIN))
    assert admin is not None

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}", json={"is_active": False}
    )
    assert response.status_code == 409
    assert response.json()["error"]["message"] == "The final active Admin cannot be changed."
