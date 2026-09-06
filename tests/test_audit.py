"""Purpose: Prove append-only, attributed, redacted security audit behavior."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.main import app
from backend.ai.provider import FakeAIProvider
from backend.audit import AuditService
from backend.security.auth import AuthenticatedPrincipal, create_user, token_digest
from db.models import Alert, AuditEvent, AuthSession, Case, RoleEnum, User
from db.session import get_db


def _event(db: Session, action: str) -> AuditEvent:
    event = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action == action)
        .order_by(AuditEvent.id.desc())
    ).first()
    assert event is not None
    return event


def _role_client(db: Session, *, role: RoleEnum, suffix: str) -> TestClient:
    token = f"audit-test-{suffix}-bearer"
    user = User(
        username=f"audit-{suffix}",
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


def test_mutations_are_attributed_and_request_correlated(
    client: TestClient, db_session: Session
) -> None:
    alert = db_session.scalar(select(Alert).where(Alert.external_id == "ALERT-1003"))
    assert alert is not None

    response = client.patch(
        f"/api/v1/alerts/{alert.id}",
        json={"status": "closed"},
        headers={"X-Request-ID": "audit-correlation-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "audit-correlation-1"
    event = _event(db_session, "alert.update")
    assert event.actor_identifier == "test-analyst"
    assert event.actor_user_id is not None
    assert event.target_id == str(alert.id)
    assert event.outcome == "succeeded"
    assert event.request_id == "audit-correlation-1"
    assert event.before_state["status"] != event.after_state["status"]


def test_domain_families_emit_safe_success_and_failure_events(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    alert = db_session.scalar(select(Alert).where(Alert.external_id == "ALERT-0005"))
    case = db_session.scalar(select(Case).where(Case.case_number == "CASE-2026-0001"))
    assert alert is not None and case is not None
    monkeypatch.setattr(
        "api.v1.endpoints.ai.build_ai_provider",
        lambda config: FakeAIProvider(
            '{"summary":"x","assessment":"y","confidence":0.7,'
            f'"evidence_refs":["alert-{alert.id}"]}}'
        ),
    )
    monkeypatch.setattr(
        "api.v1.endpoints.copilot.build_ai_provider",
        lambda config: FakeAIProvider(
            '{"answer":"x","assessment":"y","confidence":0.7,'
            f'"evidence_refs":["case-{case.id}"]}}'
        ),
    )
    monkeypatch.setattr(
        "api.v1.endpoints.reports.build_ai_provider",
        lambda config: FakeAIProvider(
            '{"executive_summary":"x","technical_timeline":[],"indicators":[],'
            '"mitre":[],"actions_recorded":[],"recommendations":[],'
            f'"evidence_refs":["case-{case.id}"]}}'
        ),
    )

    responses = [
        client.post("/api/v1/cases", json={"title": "Audited case"}),
        client.post(
            "/api/v1/rules/validate",
            json={
                "logic": {
                    "rule_type": "single",
                    "condition": {"operator": "exists", "field": "hostname"},
                }
            },
        ),
        client.post("/api/v1/ingestion/fixture/test", json={}),
        client.post(
            "/api/v1/ingestion/fixture/sync",
            json={
                "start_time": "2026-08-15T02:00:00Z",
                "end_time": "2026-08-15T03:00:00Z",
                "limit": 10,
                "dry_run": True,
            },
        ),
        client.post(f"/api/v1/alerts/{alert.id}/ai/triage", json={}),
        client.post(
            f"/api/v1/cases/{case.id}/ai/ask", json={"question": "What happened?"}
        ),
        client.post(f"/api/v1/cases/{case.id}/ai/report"),
    ]
    assert all(response.status_code < 400 for response in responses)

    actions = set(db_session.scalars(select(AuditEvent.action)))
    assert {
        "case.create",
        "rule.validate",
        "integration.test",
        "integration.sync",
        "ai.triage.request",
        "ai.copilot.request",
        "ai.report.request",
    } <= actions
    assert _event(db_session, "ai.copilot.request").details.get("question") is None


def test_denied_authorization_is_recorded_and_admin_reads_are_bounded(
    db_session: Session,
) -> None:
    def _override_get_db():  # noqa: ANN202
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with _role_client(db_session, role=RoleEnum.VIEWER, suffix="viewer") as viewer:
            denied = viewer.post("/api/v1/cases", json={"title": "Denied"})
            assert denied.status_code == 403
            assert viewer.get("/api/v1/audit-events").status_code == 403
        event = _event(db_session, "authorization.denied")
        assert event.outcome == "denied"
        assert event.details == {"permission": "read_audit"}
        with _role_client(db_session, role=RoleEnum.ADMIN, suffix="admin") as admin:
            response = admin.get(
                "/api/v1/audit-events",
                params={"action": "authorization.denied", "page_size": 1},
            )
            oversized = admin.get("/api/v1/audit-events", params={"page_size": 101})
    finally:
        app.dependency_overrides.pop(get_db, None)
    assert response.status_code == 200
    assert response.json()["page_size"] == 1
    assert all(item["action"] == "authorization.denied" for item in response.json()["items"])
    assert oversized.status_code == 422


def test_auth_and_admin_actions_are_audited(
    anonymous_client: TestClient, client: TestClient, db_session: Session
) -> None:
    user, created = create_user(
        db_session,
        username="audit-login-user",
        password="audit-login-password",
        role=RoleEnum.VIEWER,
    )
    assert created
    db_session.commit()

    failed = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "wrong-password-value"},
    )
    login = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": user.username, "password": "audit-login-password"},
    )
    logout = anonymous_client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    created_user = client.post(
        "/api/v1/admin/users",
        json={
            "username": "audit-managed-user",
            "password": "audit-managed-password",
            "role": "viewer",
        },
    )

    assert failed.status_code == 401
    assert login.status_code == 200
    assert logout.status_code == 204
    assert created_user.status_code == 201
    events = list(db_session.scalars(select(AuditEvent)))
    assert {(event.action, event.outcome) for event in events} >= {
        ("auth.login", "failed"),
        ("auth.login", "succeeded"),
        ("auth.logout", "succeeded"),
        ("admin.user.create", "succeeded"),
    }


def test_recursive_redaction_and_bounds_hide_canaries(db_session: Session) -> None:
    canary = "super-sensitive-canary"
    AuditService(db_session).record(
        action="security.redaction_test",
        outcome="succeeded",
        actor_identifier="system",
        before_state={"password": canary, "nested": {"api_key": canary}},
        after_state={"prompt": canary, "safe": f"token={canary}"},
        details={"raw_payload": {"value": canary}, "long": "a" * 2000},
    )
    db_session.commit()
    event = _event(db_session, "security.redaction_test")
    rendered = str(
        [event.before_state, event.after_state, event.details]
    )
    assert canary not in rendered
    assert "[REDACTED]" in rendered
    assert "[TRUNCATED]" in rendered


def test_audit_rows_reject_orm_update_and_delete(db_session: Session) -> None:
    event = AuditService(db_session).record(
        action="security.immutability_test", outcome="succeeded"
    )
    db_session.commit()
    event.action = "tampered"
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()

    stored = db_session.get(AuditEvent, event.id)
    assert stored is not None
    db_session.delete(stored)
    with pytest.raises(ValueError, match="append-only"):
        db_session.commit()
    db_session.rollback()
    assert db_session.get(AuditEvent, event.id) is not None


def test_audit_failure_rolls_back_domain_mutation(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from api.schemas.alert import AlertUpdate
    from api.v1.endpoints.alerts import update_alert

    alert = db_session.scalar(select(Alert).where(Alert.external_id == "ALERT-1003"))
    actor = db_session.scalar(select(User).where(User.username == "test-analyst"))
    session = db_session.scalar(select(AuthSession).where(AuthSession.user_id == actor.id))
    assert alert is not None and actor is not None and session is not None
    original_status = alert.status

    def _fail_record(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        raise RuntimeError("simulated audit persistence failure")

    monkeypatch.setattr("api.v1.endpoints.alerts.AuditService.record", _fail_record)
    with pytest.raises(RuntimeError, match="simulated audit"):
        update_alert(
            alert.id,
            AlertUpdate(status="closed"),
            AuthenticatedPrincipal(user=actor, session=session),
            db_session,
        )
    db_session.rollback()
    db_session.refresh(alert)
    assert alert.status == original_status
