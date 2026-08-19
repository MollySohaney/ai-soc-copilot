"""Purpose: Verify the API health check endpoint."""

from fastapi.testclient import TestClient

from api.main import app
from config.settings import load_config


def test_health_returns_ok() -> None:
    """Ensure the health endpoint reports service status and metadata."""
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200

    settings = load_config()
    body = response.json()
    assert body["status"] == "ok"
    assert body["app_name"] == settings.app_name
    assert body["api_version"] == "v1"
