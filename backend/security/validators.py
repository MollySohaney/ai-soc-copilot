"""Purpose: Validate uploaded files before they reach parsing logic."""

from __future__ import annotations

from pathlib import Path

from backend.security.files import normalize_upload_filename
from config.settings import AppConfig


class FileUploadValidator:
    """Enforce basic upload policy controls."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize the validator with application settings.

        Args:
            config: Loaded application configuration.
        """
        self._config = config

    def validate(self, file_name: str, content: bytes) -> str:
        """Validate file name, extension, and size.

        Args:
            file_name: Name of the uploaded file.
            content: Raw file bytes.

        Raises:
            ValueError: If validation fails.
        """
        safe_name = normalize_upload_filename(file_name)
        extension = Path(safe_name).suffix.lower().lstrip(".")
        if extension not in self._config.allowed_upload_types:
            raise ValueError(
                "Unsupported file type. Allowed types: "
                f"{', '.join(self._config.allowed_upload_types)}."
            )

        max_bytes = self._config.max_upload_size_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValueError(
                f"File exceeds the maximum size of {self._config.max_upload_size_mb} MB."
            )

        if not content:
            raise ValueError("Uploaded file is empty.")
        if b"\x00" in content:
            raise ValueError("Uploaded file contains unsupported binary content.")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Uploaded file must be UTF-8 encoded.") from error
        first_content = text.lstrip()[:1]
        if extension == "json" and first_content not in {"{", "["}:
            raise ValueError("JSON upload does not match its declared file type.")
        if extension == "csv" and "," not in text.splitlines()[0]:
            raise ValueError("CSV upload does not match its declared file type.")
        return safe_name
