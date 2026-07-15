"""Purpose: Render the MITRE Explorer placeholder page."""

from __future__ import annotations

from ..components.layout import render_page_header, render_placeholder_notice
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the MITRE Explorer placeholder page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_page_header(
        title="MITRE Explorer",
        description="Future home for ATT&CK-aligned exploration workflows.",
    )
    render_placeholder_notice(
        title="Not Yet Implemented",
        body=(
            "This page is reserved for a future MITRE ATT&CK exploration capability. "
            "The current scaffold keeps navigation and page boundaries in place without adding lookup logic."
        ),
    )
