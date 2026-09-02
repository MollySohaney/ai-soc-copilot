"""Purpose: Verify supported alert file parsing behavior."""

import pytest

from backend.parsers.alert_parser import AlertFileParser
from backend.security.files import (
    escape_spreadsheet_cell,
    export_content_type,
    safe_download_filename,
)
from backend.security.validators import FileUploadValidator
from config.settings import AppConfig


def test_parse_json_list_returns_preview_rows() -> None:
    """Ensure JSON arrays are converted into preview rows."""
    parser = AlertFileParser()

    result = parser.parse(
        file_name="alerts.json",
        content=b'[{"id": 1, "severity": "high"}, {"id": 2, "severity": "medium"}]',
    )

    assert result.metadata["file_type"] == "json"
    assert result.metadata["record_count"] == 2
    assert len(result.preview_rows) == 2


def test_parse_txt_returns_text_preview() -> None:
    """Ensure text files produce a textual preview."""
    parser = AlertFileParser()

    result = parser.parse(
        file_name="alerts.txt",
        content=b"line one\nline two\nline three",
    )

    assert result.metadata["file_type"] == "txt"
    assert "line one" in result.text_preview


@pytest.mark.parametrize(
    "file_name",
    ["../alert.json", "..%2Falert.json", "folder\\alert.json", "alert\n.json"],
)
def test_upload_rejects_traversal_and_control_characters(file_name: str) -> None:
    validator = FileUploadValidator(AppConfig())
    with pytest.raises(ValueError, match="unsafe name"):
        validator.validate(file_name, b'{"event":"safe"}')


def test_upload_enforces_extension_signature_encoding_and_size() -> None:
    validator = FileUploadValidator(AppConfig(max_upload_size_mb=1))
    with pytest.raises(ValueError, match="declared file type"):
        validator.validate("renamed.json", b"not json")
    with pytest.raises(ValueError, match="declared file type"):
        validator.validate("renamed.csv", b"single-column")
    with pytest.raises(ValueError, match="UTF-8"):
        validator.validate("alert.txt", b"\xff\xfe")
    with pytest.raises(ValueError, match="maximum size"):
        validator.validate("alert.txt", b"a" * (1_048_576 + 1))


def test_export_filename_and_spreadsheet_cells_are_safe() -> None:
    assert safe_download_filename("Case ../../ Quarterly", extension="CSV") == "Case-Quarterly.csv"
    assert "/" not in safe_download_filename("Case ../../ Quarterly", extension="CSV")
    assert escape_spreadsheet_cell("=HYPERLINK(\"https://attacker.invalid\")").startswith("'=")
    assert escape_spreadsheet_cell("normal") == "normal"
    assert export_content_type("CSV") == "text/csv; charset=utf-8"
    with pytest.raises(ValueError, match="format"):
        safe_download_filename("case", extension="../../exe")
    with pytest.raises(ValueError, match="format"):
        export_content_type("html")
