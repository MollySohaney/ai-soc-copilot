"""Purpose: Verify configuration defaults and normalization."""

import pytest

from config.settings import AppConfig


def test_config_normalizes_upload_types() -> None:
    """Ensure configured upload types are normalized to lowercase values."""
    config = AppConfig(allowed_upload_types=[" JSON ", "Csv", "txt"])

    assert config.allowed_upload_types == ["json", "csv", "txt"]


def test_config_normalizes_log_level() -> None:
    """Ensure the configured log level is uppercased."""
    config = AppConfig(log_level="debug")

    assert config.log_level == "DEBUG"


def test_safe_config_redacts_postgres_password() -> None:
    """Ensure UI-facing runtime config does not expose the database password."""
    config = AppConfig(postgres_password="super-secret")

    safe_config = config.to_safe_dict()

    assert safe_config["postgres_password"] == "[redacted]"
    assert "super-secret" not in safe_config.values()


def test_safe_config_redacts_elastic_credentials() -> None:
    """Ensure UI-facing runtime config does not expose Elastic credentials."""
    config = AppConfig(
        elastic_api_key="elastic-api-secret",
        elastic_username="elastic-user",
        elastic_password="elastic-password-secret",
    )

    safe_config = config.to_safe_dict()

    assert safe_config["elastic_username"] == "elastic-user"
    assert safe_config["elastic_api_key"] == "[redacted]"
    assert safe_config["elastic_password"] == "[redacted]"
    assert "elastic-api-secret" not in safe_config.values()
    assert "elastic-password-secret" not in safe_config.values()


def test_config_rejects_non_positive_elastic_timeout() -> None:
    """Elastic request timeouts must be positive."""
    try:
        AppConfig(elastic_request_timeout_seconds=0)
    except ValueError as error:
        assert "Elastic request timeout" in str(error)
    else:
        raise AssertionError("Expected AppConfig to reject a zero Elastic timeout.")


def test_config_rejects_non_positive_ingestion_limit() -> None:
    """Manual ingestion sync limits must be positive."""
    try:
        AppConfig(max_ingestion_sync_limit=0)
    except ValueError as error:
        assert "Maximum ingestion sync limit" in str(error)
    else:
        raise AssertionError("Expected AppConfig to reject a zero ingestion limit.")


def test_config_rejects_non_positive_ingestion_retry_attempts() -> None:
    """Ingestion retry attempts must be positive."""
    try:
        AppConfig(ingestion_retry_attempts=0)
    except ValueError as error:
        assert "Ingestion retry attempts" in str(error)
    else:
        raise AssertionError("Expected AppConfig to reject zero retry attempts.")


def test_config_rejects_negative_ingestion_retry_backoff() -> None:
    """Ingestion retry backoff cannot be negative."""
    try:
        AppConfig(ingestion_retry_backoff_seconds=-0.1)
    except ValueError as error:
        assert "Ingestion retry backoff" in str(error)
    else:
        raise AssertionError("Expected AppConfig to reject negative retry backoff.")


def test_ai_config_defaults_to_disabled_and_redacts_api_key() -> None:
    """AI is opt-in and its environment credential is never shown in safe config."""
    config = AppConfig(ai_api_key="ai-secret")

    assert config.ai_enabled is False
    assert config.to_safe_dict()["ai_api_key"] == "[redacted]"
    assert "ai-secret" not in config.to_safe_dict().values()


def test_auth_session_and_login_limits_must_be_positive() -> None:
    """Authentication expiry and brute-force settings reject unsafe values."""
    fields = (
        "auth_session_idle_minutes",
        "auth_session_absolute_hours",
        "auth_login_max_attempts",
        "auth_login_window_seconds",
    )
    for field in fields:
        try:
            AppConfig(**{field: 0})
        except ValueError as error:
            assert "Authentication limits" in str(error)
        else:
            raise AssertionError(f"Expected {field} to reject zero.")


def test_config_rejects_non_positive_ai_limits() -> None:
    """AI timeout and token limits must be positive."""
    for field, value in (("ai_request_timeout_seconds", 0), ("ai_max_input_tokens", 0), ("ai_max_output_tokens", 0)):
        try:
            AppConfig(**{field: value})
        except ValueError:
            pass
        else:
            raise AssertionError(f"Expected AppConfig to reject {field}={value}.")


def test_boundary_and_abuse_limits_must_remain_enabled() -> None:
    fields = (
        "api_max_body_bytes",
        "api_max_query_window_days",
        "abuse_rate_window_seconds",
        "login_rate_limit",
        "login_concurrency_limit",
        "ai_rate_limit",
        "ai_concurrency_limit",
        "ingestion_rate_limit",
        "ingestion_concurrency_limit",
        "detection_rate_limit",
        "detection_concurrency_limit",
    )
    for field in fields:
        with pytest.raises(ValueError, match="boundary limits"):
            AppConfig(**{field: 0})


def test_cors_origins_and_upload_extensions_are_narrowly_validated() -> None:
    for origin in ("*", "file:///tmp/app", "https://user:password@example.com"):
        with pytest.raises(ValueError, match="explicit HTTP"):
            AppConfig(frontend_origins=[origin])
    with pytest.raises(ValueError, match="must not contain duplicates"):
        AppConfig(frontend_origins=["https://example.com", "https://example.com"])
    with pytest.raises(ValueError, match="json, csv, or txt"):
        AppConfig(allowed_upload_types=["html"])
