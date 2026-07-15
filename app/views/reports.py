"""Purpose: Render the reports placeholder page."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_page_header, render_placeholder_notice
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the Reports page.

    Args:
        config: Application configuration.
    """
    render_page_header(
        title="Reports",
        description="Scaffolded reporting area for future analyst outputs and evidence summaries.",
    )
    render_placeholder_notice(
        title="Report Generation Pending",
        body=(
            "Report workflows are intentionally deferred until alert ingestion, normalization, "
            "and analysis boundaries are established."
        ),
    )

    st.subheader("Planned Outputs")
    st.markdown(
        "- Executive incident summaries\n"
        "- Analyst evidence notes\n"
        "- Detection coverage snapshots\n"
        "- AI-assisted triage explainability artifacts"
    )
