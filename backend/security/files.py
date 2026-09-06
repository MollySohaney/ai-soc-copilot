"""Purpose: Normalize untrusted filenames and make spreadsheet exports inert."""

from __future__ import annotations

import re
from pathlib import PurePath
from urllib.parse import unquote

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_SAFE_DOWNLOAD_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]+")
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")
_EXPORT_CONTENT_TYPES = {
    "csv": "text/csv; charset=utf-8",
    "json": "application/json",
    "md": "text/markdown; charset=utf-8",
    "pdf": "application/pdf",
}


def normalize_upload_filename(file_name: str) -> str:
    """Return a basename only when no traversal, encoding, or controls are present."""
    decoded = file_name
    for _ in range(3):
        next_value = unquote(decoded)
        if next_value == decoded:
            break
        decoded = next_value
    if (
        not decoded
        or len(decoded) > 255
        or _CONTROL_CHARACTERS.search(decoded)
        or "/" in decoded
        or "\\" in decoded
        or decoded in {".", ".."}
        or PurePath(decoded).name != decoded
    ):
        raise ValueError("Uploaded file has an unsafe name.")
    return decoded


def safe_download_filename(label: str, *, extension: str) -> str:
    """Generate a bounded attachment filename from a non-secret display label."""
    safe_extension = extension.lower().lstrip(".")
    if not re.fullmatch(r"[a-z0-9]{1,10}", safe_extension):
        raise ValueError("Invalid export format.")
    normalized = _SAFE_DOWNLOAD_CHARACTERS.sub("-", label.strip()).strip(".-_")
    normalized = normalized[:100] or "export"
    return f"{normalized}.{safe_extension}"


def escape_spreadsheet_cell(value: object) -> str:
    """Prefix formula-like CSV values so spreadsheet software treats them as text."""
    rendered = "" if value is None else str(value)
    if rendered.startswith(_FORMULA_PREFIXES):
        return "'" + rendered
    return rendered


def export_content_type(extension: str) -> str:
    """Map an allowlisted export selector to a server-chosen content type."""
    try:
        return _EXPORT_CONTENT_TYPES[extension.lower().lstrip(".")]
    except KeyError as error:
        raise ValueError("Invalid export format.") from error
