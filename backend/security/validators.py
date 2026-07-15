"""Purpose: Validate uploaded files before they reach parsing logic."""

from __future__ import annotations

from pathlib import Path

from config.settings import AppConfig


class FileUploadValidator:
    """Enforce basic upload policy controls."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize the validator with application settings.

        Args:
            config: Loaded application configuration.
        """
        self._config = config

    def validate(self, file_name: str, content: bytes) -> None:
        """Validate file name, extension, and size.

        Args:
            file_name: Name of the uploaded file.
            content: Raw file bytes.

        Raises:
            ValueError: If validation fails.
        """
        extension = Path(file_name).suffix.lower().lstrip(".")
        if extension not in self._config.allowed_upload_types:
            raise ValueError(
                f"Unsupported file type '{extension}'. Allowed types: "
                f"{', '.join(self._config.allowed_upload_types)}."
            )

        max_bytes = self._config.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(
                f"File exceeds the maximum size of {self._config.max_upload_size_mb} MB."
            )

        if not file_name.strip():
            raise ValueError("Uploaded file must have a valid name.")

        if not content:
            raise ValueError("Uploaded file is empty.")
