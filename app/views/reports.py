"""Purpose: Render the reports placeholder page."""

from __future__ import annotations

from ..components.layout import render_html_block, render_placeholder_notice, render_stat_list
from ..components.theme import render_shell_end, render_shell_start
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the Reports page.

    Args:
        config: Application configuration.
    """
    render_shell_start(
        title="Reports",
        description="Scaffolded reporting area for analyst narratives, evidence exports, and executive summaries.",
        breadcrumb="SOC workspace / reports",
        status_chips=[
            ("Output mode", "Placeholder"),
            ("Export target", "Local only"),
        ],
    )
    render_html_block('<div class="soc-grid"><div class="soc-stack"><div class="soc-card glow">')
    render_placeholder_notice(
        title="Report Generation Pending",
        body=(
            "Report workflows are intentionally deferred until alert ingestion, normalization, "
            "and analysis boundaries are established."
        ),
    )
    render_html_block("</div><div class=\"soc-card\"><div class=\"soc-card-label\">Planned outputs</div>")
    render_stat_list(
        [
            ("Executive incident summary", "Planned"),
            ("Analyst evidence notes", "Planned"),
            ("Detection coverage snapshot", "Planned"),
            ("AI explainability artifact", "Planned"),
        ]
    )
    render_html_block("</div></div><div class=\"soc-stack\"><div class=\"soc-card glow\"><div class=\"soc-card-label\">Reporting posture</div>")
    render_stat_list(
        [
            ("Persistence layer", "Not implemented"),
            ("Export format", "TBD"),
            ("Approval workflow", "Not implemented"),
            ("Audit trail", "Planned"),
        ]
    )
    render_html_block("</div></div></div>")
    render_shell_end()
