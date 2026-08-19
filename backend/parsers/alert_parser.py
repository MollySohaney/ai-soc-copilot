"""Purpose: Parse supported alert file formats into a UI-friendly preview."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

from backend.models.alert_file import AlertPreview


class AlertFileParser:
    """Parse supported files into normalized preview structures."""

    def parse(self, file_name: str, content: bytes) -> AlertPreview:
        """Parse an uploaded file into a preview model.

        Args:
            file_name: Name of the uploaded file.
            content: Raw file content.

        Returns:
            Parsed preview object.

        Raises:
            ValueError: If the file extension is unsupported or decoding fails.
        """
        extension = Path(file_name).suffix.lower().lstrip(".")
        try:
            text_content = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError("Uploaded file must be UTF-8 encoded.") from error

        if extension == "json":
            return self._parse_json(text_content=text_content, file_name=file_name)
        if extension == "csv":
            return self._parse_csv(text_content=text_content, file_name=file_name)
        if extension == "txt":
            return self._parse_txt(text_content=text_content, file_name=file_name)

        raise ValueError(f"Unsupported file type: {extension}")

    def _parse_json(self, text_content: str, file_name: str) -> AlertPreview:
        """Parse JSON content into preview rows."""
        payload = json.loads(text_content)
        preview_rows: list[dict[str, Any]]

        if isinstance(payload, list):
            preview_rows = [item for item in payload[:5] if isinstance(item, dict)]
            item_count = len(payload)
        elif isinstance(payload, dict):
            preview_rows = [payload]
            item_count = len(payload.keys())
        else:
            preview_rows = [{"value": payload}]
            item_count = 1

        return AlertPreview(
            metadata={
                "file_name": file_name,
                "file_type": "json",
                "record_count": item_count,
            },
            preview_rows=preview_rows,
            text_preview=None,
        )

    def _parse_csv(self, text_content: str, file_name: str) -> AlertPreview:
        """Parse CSV content into preview rows."""
        reader = csv.DictReader(io.StringIO(text_content))
        rows = list(reader)
        return AlertPreview(
            metadata={
                "file_name": file_name,
                "file_type": "csv",
                "record_count": len(rows),
                "columns": reader.fieldnames or [],
            },
            preview_rows=rows[:5],
            text_preview=None,
        )

    def _parse_txt(self, text_content: str, file_name: str) -> AlertPreview:
        """Parse TXT content into a short textual preview."""
        lines = text_content.splitlines()
        return AlertPreview(
            metadata={
                "file_name": file_name,
                "file_type": "txt",
                "line_count": len(lines),
            },
            preview_rows=[],
            text_preview="\n".join(lines[:20]),
        )
