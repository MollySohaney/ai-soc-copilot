"""Purpose: Verify supported alert file parsing behavior."""

from backend.parsers.alert_parser import AlertFileParser


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
