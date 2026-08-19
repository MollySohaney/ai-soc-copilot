"""Purpose: Configure structured logging for the application."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.config import dictConfig
from pathlib import Path
from typing import Any

from config.settings import AppConfig


class JsonFormatter(logging.Formatter):
    """Format log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record to JSON.

        Args:
            record: Standard logging record.

        Returns:
            JSON log line.
        """
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        standard_fields = {
            "args",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }

        extra_fields = {
            key: value for key, value in record.__dict__.items() if key not in standard_fields
        }
        if extra_fields:
            payload["context"] = extra_fields

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def initialize_logging(config: AppConfig) -> None:
    """Initialize application logging based on the loaded configuration.

    Args:
        config: Loaded application configuration.
    """
    log_directory = Path(config.log_dir)
    log_directory.mkdir(parents=True, exist_ok=True)

    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": "backend.utils.logging.JsonFormatter",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "level": config.log_level,
                    "formatter": "json",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "level": config.log_level,
                    "formatter": "json",
                    "filename": str(log_directory / "app.log"),
                    "encoding": "utf-8",
                },
            },
            "root": {
                "level": config.log_level,
                "handlers": ["console", "file"],
            },
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance for the requested module.

    Args:
        name: Module or subsystem name.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
