"""Purpose: Coordinate alert upload validation and parsing."""

from __future__ import annotations

from backend.models.alert_file import UploadResult
from backend.parsers.alert_parser import AlertFileParser
from backend.security.validators import FileUploadValidator
from backend.utils.logging import get_logger
from config.settings import AppConfig


class AlertUploadService:
    """Handle supported alert upload workflows."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize the upload workflow dependencies.

        Args:
            config: Loaded application configuration.
        """
        self._config = config
        self._validator = FileUploadValidator(config=config)
        self._parser = AlertFileParser()
        self._logger = get_logger(__name__)

    def process_upload(self, file_name: str, content: bytes) -> UploadResult:
        """Validate and parse an uploaded alert file.

        Args:
            file_name: Name of the uploaded file.
            content: Raw file bytes.

        Returns:
            Upload result for UI consumption.
        """
        try:
            self._validator.validate(file_name=file_name, content=content)
            preview = self._parser.parse(file_name=file_name, content=content)
        except ValueError as error:
            self._logger.warning(
                "Upload rejected",
                extra={"file_name": file_name, "reason": str(error)},
            )
            return UploadResult(is_valid=False, message=str(error))

        self._logger.info(
            "Upload processed",
            extra={"file_name": file_name, "file_type": preview.metadata.get("file_type")},
        )
        return UploadResult(
            is_valid=True,
            message="Upload validated successfully.",
            preview=preview,
        )
