"""Purpose: Render the MITRE Explorer placeholder page."""

from __future__ import annotations

from ..components.layout import render_html_block, render_placeholder_notice
from ..components.theme import render_shell_end, render_shell_start
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the MITRE Explorer placeholder page.

    Args:
        config: Application configuration.
    """
    render_shell_start(
        title="MITRE Explorer",
        description="Reserved space for ATT&CK-aligned mapping, tactic exploration, and detection coverage views.",
        breadcrumb="SOC workspace / mitre",
        status_chips=[
            ("Dataset", "Not loaded"),
            ("Lookup mode", "Disabled"),
        ],
    )
    render_html_block('<div class="soc-card glow">')
    render_placeholder_notice(
        title="Not Yet Implemented",
        body=(
            "This page is reserved for a future MITRE ATT&CK exploration capability. "
            "The current scaffold keeps navigation and page boundaries in place without adding lookup logic."
        ),
    )
    render_html_block("</div>")
    render_shell_end()
