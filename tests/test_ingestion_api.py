"""Purpose: Verify telemetry ingestion API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from api.main import app
from config.settings import AppConfig, load_config
from db.models import Event, IngestionCheckpoint, IngestionRun


SYNC_BODY = {
    "start_time": "2026-08-15T02:00:00Z",
    "end_time": "2026-08-15T04:00:00Z",
    "limit": 3,
    "source_name": "fixture-api",
}


def test_fixture_connection_test(client: TestClient) -> None:
    """Fixture provider exposes a sanitized connection test result."""
    response = client.post("/api/v1/ingestion/fixture/test", json={"source_name": "fixture-api"})

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "provider": "fixture",
        "source_name": "fixture-api",
        "ok": True,
        "message": "Fixture ingestion source is available.",
        "details": {},
    }


def test_fixture_manual_sync_persists_events_and_checkpoint(
    client: TestClient, db_session: Session
) -> None:
    """Manual fixture sync persists normalized events and advances checkpoint."""
    before_events = db_session.scalar(select(func.count()).select_from(Event))

    response = client.post("/api/v1/ingestion/fixture/sync", json=SYNC_BODY)

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fixture"
    assert body["source_name"] == "fixture-api"
    assert body["status"] == "succeeded"
    assert body["fetched_count"] == 3
    assert body["normalized_count"] == 3
    assert body["persisted_count"] == 3
    assert body["checkpoint_advanced"] is True
    assert body["errors"] == []
    assert db_session.scalar(select(func.count()).select_from(Event)) == before_events + 3

    checkpoint = db_session.scalar(
        select(IngestionCheckpoint).where(IngestionCheckpoint.source_name == "fixture-api")
    )
    assert checkpoint is not None
    assert checkpoint.checkpoint == {"offset": 3}


def test_fixture_dry_run_does_not_write_events_or_checkpoint(
    client: TestClient, db_session: Session
) -> None:
    """Dry-run reports sync counts without writing events or checkpoint state."""
    before_events = db_session.scalar(select(func.count()).select_from(Event))

    response = client.post(
        "/api/v1/ingestion/fixture/sync",
        json={**SYNC_BODY, "source_name": "fixture-dry-run", "dry_run": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "dry_run"
    assert body["dry_run"] is True
    assert body["persisted_count"] == 0
    assert body["checkpoint_advanced"] is False
    assert db_session.scalar(select(func.count()).select_from(Event)) == before_events
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(IngestionCheckpoint)
            .where(IngestionCheckpoint.source_name == "fixture-dry-run")
        )
        == 0
    )


def test_ingestion_status_returns_latest_run_and_checkpoints(client: TestClient) -> None:
    """Status exposes current run/checkpoint state without secrets."""
    client.post("/api/v1/ingestion/fixture/sync", json=SYNC_BODY)

    response = client.get("/api/v1/ingestion/status")

    assert response.status_code == 200
    body = response.json()
    assert body["latest_run"]["provider"] == "fixture"
    assert body["latest_run"]["source_name"] == "fixture-api"
    assert "password" not in response.text.lower()
    assert "api_key" not in response.text.lower()
    assert any(
        checkpoint["source_name"] == "fixture-api"
        and checkpoint["checkpoint"] == {"offset": 3}
        for checkpoint in body["checkpoints"]
    )


def test_ingestion_run_history_is_paginated(client: TestClient) -> None:
    """Run history returns newest ingestion runs with pagination metadata."""
    client.post("/api/v1/ingestion/fixture/sync", json=SYNC_BODY)

    response = client.get("/api/v1/ingestion/runs", params={"page": 1, "page_size": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["page"] == 1
    assert body["page_size"] == 1
    assert body["total"] >= 1
    assert len(body["items"]) == 1
    assert body["items"][0]["provider"] == "fixture"


def test_unsupported_ingestion_provider_returns_404(client: TestClient) -> None:
    """Unknown provider names are rejected explicitly."""
    response = client.post("/api/v1/ingestion/unknown/test", json={})

    assert response.status_code == 404
    assert response.json()["detail"] == "Unsupported ingestion provider: unknown"


def test_elastic_missing_config_returns_sanitized_400(client: TestClient) -> None:
    """Elastic endpoints fail safely when required non-secret config is absent."""

    def _config_override() -> AppConfig:
        return AppConfig(
            elastic_url=None,
            elastic_api_key="should-not-leak",
            elastic_password="should-not-leak",
        )

    app.dependency_overrides[load_config] = _config_override
    try:
        response = client.post("/api/v1/ingestion/elastic/test", json={})
    finally:
        app.dependency_overrides.pop(load_config, None)

    assert response.status_code == 400
    assert response.json()["detail"] == "ELASTIC_URL is required for Elastic ingestion."
    assert "should-not-leak" not in response.text


def test_sync_requires_valid_time_window(client: TestClient) -> None:
    """Manual sync requests must be bounded by a forward time window."""
    response = client.post(
        "/api/v1/ingestion/fixture/sync",
        json={
            "start_time": "2026-08-15T04:00:00Z",
            "end_time": "2026-08-15T02:00:00Z",
            "limit": 3,
        },
    )

    assert response.status_code == 422


def test_sync_enforces_configured_ingestion_limit(client: TestClient) -> None:
    """Manual sync requests cannot exceed the configured ingestion limit."""

    def _config_override() -> AppConfig:
        return AppConfig(max_ingestion_sync_limit=2)

    app.dependency_overrides[load_config] = _config_override
    try:
        response = client.post("/api/v1/ingestion/fixture/sync", json=SYNC_BODY)
    finally:
        app.dependency_overrides.pop(load_config, None)

    assert response.status_code == 422
    assert response.json()["detail"] == "limit must be less than or equal to 2"
