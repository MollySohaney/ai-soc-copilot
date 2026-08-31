"""Purpose: Centralize application configuration loading and validation."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class AppConfig(BaseModel):
    """Represent the runtime configuration for AI SOC Copilot."""

    app_name: str = Field(default="AI SOC Copilot")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8501)
    log_level: str = Field(default="INFO")
    log_dir: str = Field(default="logs")
    max_upload_size_mb: int = Field(default=10)
    allowed_upload_types: list[str] = Field(default_factory=lambda: ["json", "csv", "txt"])
    api_version: str = Field(default="v1")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_base_url: str = Field(default="http://localhost:8000")
    frontend_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8501"])
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="ai_soc_copilot")
    postgres_user: str = Field(default="postgres")
    postgres_password: str = Field(default="postgres")
    elastic_url: str | None = Field(default=None)
    elastic_index_pattern: str = Field(default="logs-*")
    elastic_source_name: str = Field(default="elastic-default")
    elastic_api_key: str | None = Field(default=None)
    elastic_username: str | None = Field(default=None)
    elastic_password: str | None = Field(default=None)
    elastic_request_timeout_seconds: int = Field(default=10)
    elastic_verify_certs: bool = Field(default=True)
    max_ingestion_sync_limit: int = Field(default=1000)
    ingestion_retry_attempts: int = Field(default=3)
    ingestion_retry_backoff_seconds: float = Field(default=0.5)

    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy database URL from the configured Postgres settings.

        Returns:
            A postgresql+psycopg connection URL.
        """
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        """Normalize the configured log level.

        Args:
            value: Raw log level value.

        Returns:
            Normalized uppercase log level.
        """
        return value.upper()

    @field_validator("allowed_upload_types")
    @classmethod
    def validate_upload_types(cls, value: list[str]) -> list[str]:
        """Normalize and validate allowed upload extensions.

        Args:
            value: Configured upload types.

        Returns:
            Normalized upload types.

        Raises:
            ValueError: If no types are configured.
        """
        normalized = [item.strip().lower() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one upload type must be configured.")
        return normalized

    @field_validator("max_upload_size_mb")
    @classmethod
    def validate_max_upload_size(cls, value: int) -> int:
        """Ensure the configured upload size is positive.

        Args:
            value: Configured maximum upload size in megabytes.

        Returns:
            Validated maximum upload size.

        Raises:
            ValueError: If the configured size is not positive.
        """
        if value <= 0:
            raise ValueError("Maximum upload size must be greater than zero.")
        return value

    @field_validator("elastic_request_timeout_seconds")
    @classmethod
    def validate_elastic_timeout(cls, value: int) -> int:
        """Ensure Elastic requests use a positive timeout."""
        if value <= 0:
            raise ValueError("Elastic request timeout must be greater than zero.")
        return value

    @field_validator("max_ingestion_sync_limit")
    @classmethod
    def validate_ingestion_limit(cls, value: int) -> int:
        """Ensure manual ingestion sync limits are positive."""
        if value <= 0:
            raise ValueError("Maximum ingestion sync limit must be greater than zero.")
        return value

    @field_validator("ingestion_retry_attempts")
    @classmethod
    def validate_ingestion_retry_attempts(cls, value: int) -> int:
        """Ensure ingestion retry attempts are positive."""
        if value <= 0:
            raise ValueError("Ingestion retry attempts must be greater than zero.")
        return value

    @field_validator("ingestion_retry_backoff_seconds")
    @classmethod
    def validate_ingestion_retry_backoff(cls, value: float) -> float:
        """Ensure ingestion retry backoff is not negative."""
        if value < 0:
            raise ValueError("Ingestion retry backoff must not be negative.")
        return value

    @field_validator("frontend_origins")
    @classmethod
    def validate_frontend_origins(cls, value: list[str]) -> list[str]:
        """Normalize and validate configured frontend origins.

        Args:
            value: Configured frontend origins.

        Returns:
            Normalized frontend origins.

        Raises:
            ValueError: If no origins are configured.
        """
        normalized = [item.strip() for item in value if item.strip()]
        if not normalized:
            raise ValueError("At least one frontend origin must be configured.")
        return normalized

    def to_safe_dict(self) -> dict[str, str | int | bool | list[str]]:
        """Return a UI-safe configuration view.

        Returns:
            Sanitized configuration data for display.
        """
        safe_config = self.model_dump(
            exclude={"postgres_password", "elastic_api_key", "elastic_password"}
        )
        safe_config["postgres_password"] = "[redacted]"
        safe_config["elastic_api_key"] = "[redacted]" if self.elastic_api_key else None
        safe_config["elastic_password"] = "[redacted]" if self.elastic_password else None
        return safe_config


@lru_cache(maxsize=1)
def load_config() -> AppConfig:
    """Load application configuration from environment variables.

    Returns:
        Validated application configuration.
    """
    load_dotenv()

    upload_types = os.getenv("ALLOWED_UPLOAD_TYPES", "json,csv,txt")
    frontend_origins = os.getenv("FRONTEND_ORIGIN", "http://localhost:8501")
    return AppConfig(
        app_name=os.getenv("APP_NAME", "AI SOC Copilot"),
        environment=os.getenv("APP_ENV", "development"),
        debug=os.getenv("APP_DEBUG", "true").lower() == "true",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8501")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        log_dir=os.getenv("LOG_DIR", "logs"),
        max_upload_size_mb=int(os.getenv("MAX_UPLOAD_SIZE_MB", "10")),
        allowed_upload_types=upload_types.split(","),
        api_version=os.getenv("API_VERSION", "v1"),
        api_host=os.getenv("API_HOST", "0.0.0.0"),
        api_port=int(os.getenv("API_PORT", "8000")),
        api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        frontend_origins=frontend_origins.split(","),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost"),
        postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
        postgres_db=os.getenv("POSTGRES_DB", "ai_soc_copilot"),
        postgres_user=os.getenv("POSTGRES_USER", "postgres"),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        elastic_url=os.getenv("ELASTIC_URL") or None,
        elastic_index_pattern=os.getenv("ELASTIC_INDEX_PATTERN", "logs-*"),
        elastic_source_name=os.getenv("ELASTIC_SOURCE_NAME", "elastic-default"),
        elastic_api_key=os.getenv("ELASTIC_API_KEY") or None,
        elastic_username=os.getenv("ELASTIC_USERNAME") or None,
        elastic_password=os.getenv("ELASTIC_PASSWORD") or None,
        elastic_request_timeout_seconds=int(os.getenv("ELASTIC_REQUEST_TIMEOUT_SECONDS", "10")),
        elastic_verify_certs=os.getenv("ELASTIC_VERIFY_CERTS", "true").lower() == "true",
        max_ingestion_sync_limit=int(os.getenv("MAX_INGESTION_SYNC_LIMIT", "1000")),
        ingestion_retry_attempts=int(os.getenv("INGESTION_RETRY_ATTEMPTS", "3")),
        ingestion_retry_backoff_seconds=float(os.getenv("INGESTION_RETRY_BACKOFF_SECONDS", "0.5")),
    )
