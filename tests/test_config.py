"""Purpose: Verify configuration defaults and normalization."""

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
