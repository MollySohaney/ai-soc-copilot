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
        return self.model_dump()


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
    )
