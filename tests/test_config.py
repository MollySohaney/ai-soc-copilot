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
