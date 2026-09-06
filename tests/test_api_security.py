"""Purpose: Exercise hostile and boundary HTTP inputs against the hardened API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app
from backend.ai.provider import UnavailableAIProvider
from backend.security.abuse_limiter import AbuseLimiter, get_abuse_limiter
from backend.security.auth import create_user
from config.settings import AppConfig, load_config
from db.models import RoleEnum


def _assert_error(response, *, status: int, code: str) -> dict:  # noqa: ANN001
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == response.headers["X-Request-ID"]
    return body["error"]


def test_body_media_query_and_path_boundaries(client: TestClient) -> None:
    oversized = client.post(
        "/api/v1/rules/validate",
        content=b"x" * 1_048_577,
        headers={"Content-Type": "application/json"},
    )
    unsupported = client.post(
        "/api/v1/rules/validate",
        content=b"{}",
        headers={"Content-Type": "text/plain"},
    )
    duplicate = client.get("/api/v1/alerts?page=1&page=2")
    duplicate_json = client.patch(
        "/api/v1/alerts/1",
        content=b'{"status":"closed","status":"new"}',
        headers={"Content-Type": "application/json"},
    )
    traversal = client.get("/api/v1/%2e%2e/alerts")
    negative_id = client.get("/api/v1/alerts/-1")

    _assert_error(oversized, status=413, code="request_too_large")
    _assert_error(unsupported, status=415, code="unsupported_media_type")
    _assert_error(duplicate, status=400, code="bad_request")
    _assert_error(duplicate_json, status=400, code="bad_request")
    _assert_error(traversal, status=400, code="bad_request")
    validation = _assert_error(negative_id, status=422, code="validation_error")
    assert "-1" not in str(validation)


def test_validation_errors_do_not_echo_secrets(
    anonymous_client: TestClient,
) -> None:
    canary = "never-echo-this-secret-canary"
    response = anonymous_client.post(
        "/api/v1/auth/login",
        json={"username": "user", "password": canary + ("x" * 1100)},
        headers={"X-Request-ID": "safe-correlation-id"},
    )

    error = _assert_error(response, status=422, code="validation_error")
    assert canary not in response.text
    assert error["request_id"] == "safe-correlation-id"
    assert all("input" not in detail for detail in error["details"])


def test_unhandled_and_upstream_errors_are_generic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "api.v1.endpoints.ai.build_ai_provider",
        lambda _config: (_ for _ in ()).throw(
            RuntimeError("postgres password=secret provider internals")
        ),
    )
    with TestClient(app, raise_server_exceptions=False, headers=client.headers) as safe_client:
        response = safe_client.post("/api/v1/alerts/1/ai/triage", json={})

    _assert_error(response, status=500, code="internal_error")
    assert "secret" not in response.text
    assert "provider internals" not in response.text


def test_cors_allows_only_configured_frontend_and_minimum_headers(
    anonymous_client: TestClient,
) -> None:
    allowed = anonymous_client.options(
        "/api/v1/alerts",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,x-request-id",
        },
    )
    denied = anonymous_client.options(
        "/api/v1/alerts",
        headers={
            "Origin": "https://attacker.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:8501"
    assert allowed.headers.get("access-control-allow-credentials") is None
    assert "authorization" in allowed.headers["access-control-allow-headers"].lower()
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
    assert denied.json()["error"]["code"] == "cors_denied"


def test_all_expensive_route_families_return_retry_metadata(
    client: TestClient,
    anonymous_client: TestClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # noqa: ANN001
    config = AppConfig(
        login_rate_limit=1,
        ai_rate_limit=1,
        ingestion_rate_limit=1,
        detection_rate_limit=1,
    )
    app.dependency_overrides[load_config] = lambda: config
    user, _created = create_user(
        db_session,
        username="rate-user",
        password="rate-user-password",
        role=RoleEnum.VIEWER,
    )
    db_session.commit()
    monkeypatch.setattr(
        "api.v1.endpoints.ai.build_ai_provider", lambda _config: UnavailableAIProvider()
    )
    try:
        assert anonymous_client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "wrong-password"},
        ).status_code == 401
        login_limited = anonymous_client.post(
            "/api/v1/auth/login",
            json={"username": user.username, "password": "different-wrong-password"},
        )

        assert client.post("/api/v1/ingestion/fixture/test", json={}).status_code == 200
        ingestion_limited = client.post("/api/v1/ingestion/fixture/test", json={})

        rule_body = {
            "logic": {
                "rule_type": "single",
                "condition": {"operator": "exists", "field": "hostname"},
            }
        }
        assert client.post("/api/v1/rules/validate", json=rule_body).status_code == 200
        detection_limited = client.post("/api/v1/rules/validate", json=rule_body)

        assert client.post("/api/v1/alerts/1/ai/triage", json={}).status_code == 201
        ai_limited = client.post("/api/v1/alerts/1/ai/triage", json={})
    finally:
        app.dependency_overrides.pop(load_config, None)

    for response in (
        login_limited,
        ingestion_limited,
        detection_limited,
        ai_limited,
    ):
        _assert_error(response, status=429, code="rate_limited")
        assert int(response.headers["Retry-After"]) >= 1


def test_rate_limit_cannot_be_bypassed_by_forwarded_headers_and_recovers(
    client: TestClient,
) -> None:
    now = [100.0]
    limiter = AbuseLimiter(clock=lambda: now[0])
    config = AppConfig(ingestion_rate_limit=1, abuse_rate_window_seconds=10)
    app.dependency_overrides[get_abuse_limiter] = lambda: limiter
    app.dependency_overrides[load_config] = lambda: config
    try:
        first = client.post(
            "/api/v1/ingestion/fixture/test",
            json={},
            headers={"X-Forwarded-For": "198.51.100.1"},
        )
        bypass = client.post(
            "/api/v1/ingestion/fixture/test",
            json={},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
        now[0] += 11
        recovered = client.post("/api/v1/ingestion/fixture/test", json={})
    finally:
        app.dependency_overrides.pop(get_abuse_limiter, None)
        app.dependency_overrides.pop(load_config, None)

    assert first.status_code == 200
    assert bypass.status_code == 429
    assert recovered.status_code == 200


def test_concurrency_slots_are_identity_and_scope_specific() -> None:
    limiter = AbuseLimiter(clock=lambda: 100.0)
    first_key = limiter.key(scope="ai", identity="user:1")
    other_key = limiter.key(scope="ai", identity="user:2")
    lease, _ = limiter.acquire(
        first_key, max_requests=10, window_seconds=60, max_concurrent=1
    )
    blocked, retry_after = limiter.acquire(
        first_key, max_requests=10, window_seconds=60, max_concurrent=1
    )
    other, _ = limiter.acquire(
        other_key, max_requests=10, window_seconds=60, max_concurrent=1
    )

    assert lease is not None and blocked is None and retry_after == 1
    assert other is not None
    lease.release()
    recovered, _ = limiter.acquire(
        first_key, max_requests=10, window_seconds=60, max_concurrent=1
    )
    assert recovered is not None


def test_time_windows_and_history_pages_are_bounded(client: TestClient) -> None:
    broad = client.get(
        "/api/v1/alerts",
        params={
            "start_time": "2026-01-01T00:00:00Z",
            "end_time": "2026-03-01T00:00:00Z",
        },
    )
    inverted = client.get(
        "/api/v1/dashboard/severity-distribution",
        params={
            "start_time": "2026-02-01T00:00:00Z",
            "end_time": "2026-01-01T00:00:00Z",
        },
    )
    assert broad.status_code == inverted.status_code == 422
    assert client.get("/api/v1/dashboard/alert-trends?days=366").status_code == 422
    assert client.get("/api/v1/alerts/1/events?page_size=101").status_code == 422
    assert client.get("/api/v1/cases/1/activities?page_size=101").status_code == 422
    assert client.get("/api/v1/alerts/1/ai/history?page_size=101").status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/alerts",
        "/api/v1/events",
        "/api/v1/cases",
        "/api/v1/cases/1/activities",
        "/api/v1/rules",
        "/api/v1/rules/1/runs",
        "/api/v1/ingestion/runs",
        "/api/v1/audit-events",
        "/api/v1/alerts/1/events",
        "/api/v1/alerts/1/ai/history",
        "/api/v1/cases/1/ai/history",
        "/api/v1/admin/users",
    ],
)
def test_every_list_or_history_page_enforces_the_common_maximum(
    client: TestClient, path: str
) -> None:
    response = client.get(path, params={"page_size": 101})
    _assert_error(response, status=422, code="validation_error")


def test_unknown_fields_controls_and_invalid_enums_are_rejected(
    client: TestClient,
) -> None:
    assert client.patch(
        "/api/v1/alerts/1", json={"status": "not-a-status"}
    ).status_code == 422
    assert client.post(
        "/api/v1/cases", json={"title": "case", "unexpected": "field"}
    ).status_code == 422
    control = client.get("/api/v1/alerts?q=hello%0Aworld")
    _assert_error(control, status=400, code="bad_request")
