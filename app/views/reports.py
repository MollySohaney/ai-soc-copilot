"""Purpose: Render the Incident Reports listing and report preview."""

from __future__ import annotations

import streamlit as st

from ..components.layout import (
    render_bullet_list,
    render_data_table,
    render_html_block,
    render_metric_grid,
    render_timeline,
)
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import REPORT_METRICS, REPORT_PREVIEW, REPORTS
from config.settings import AppConfig


def _render_table() -> None:
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Reports</div>')
        render_data_table(
            columns=["Report", "Investigation", "Severity", "Status", "Created", "Format"],
            rows=REPORTS,
            keys=["report", "investigation", "severity", "status", "created", "format"],
            severity_key="severity",
            status_key="status",
            strong_keys=["report"],
        )
        render_html_block(
            '<div class="soc-footer">Select a report below to preview its contents and export options.</div>'
        )


def _render_preview() -> None:
    preview = REPORT_PREVIEW
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block(
            f"""
            <div class="soc-section-title">Report Preview</div>
            <h3 class="soc-card-title" style="font-size:1.2rem;">{preview["title"]}</h3>
            <div class="soc-card-label" style="margin-top:1rem;">EXECUTIVE SUMMARY</div>
            <p class="soc-note">{preview["executive_summary"]}</p>
            <div class="soc-card-label" style="margin-top:1rem;">INCIDENT OVERVIEW</div>
            """
        )
        overview_items = "".join(
            f"<li><span>{key}</span><strong>{value}</strong></li>" for key, value in preview["incident_overview"].items()
        )
        render_html_block(f'<ul class="soc-list">{overview_items}</ul>')

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">TIMELINE</div>')
        render_timeline(preview["timeline"])

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">MITRE ATT&amp;CK MAPPING</div>')
        render_bullet_list(preview["mitre"])

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">INDICATORS OF COMPROMISE</div>')
        ioc_items = "".join(f"<li><span>{ioc['type']}</span><strong>{ioc['value']}</strong></li>" for ioc in preview["iocs"])
        render_html_block(f'<ul class="soc-list">{ioc_items}</ul>')

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">FINDINGS</div>')
        render_bullet_list(preview["findings"])

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">CONTAINMENT ACTIONS</div>')
        render_bullet_list(preview["containment_actions"])

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">RECOMMENDATIONS</div>')
        render_bullet_list(preview["recommendations"])

        render_html_block('<div class="soc-card-label" style="margin-top:1rem;">ANALYST NOTES</div>')
        render_html_block(f'<p class="soc-note">{preview["analyst_notes"]}</p>')

    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("Export PDF", type="primary", use_container_width=True, key="export_pdf")
    with col2:
        st.button("Export DOCX", use_container_width=True, key="export_docx")
    with col3:
        st.button("Export Markdown", use_container_width=True, key="export_md")


def render(config: AppConfig) -> None:
    """Render the Reports page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Incident Reports",
        description="Review and export security investigation reports.",
        breadcrumb="SOC workspace / reports",
        status_chips=[("Export target", "Local only")],
    )

    col_header, col_action = st.columns([4, 1])
    with col_action:
        st.button("Generate Report", type="primary", use_container_width=True, key="generate_report_cta")

    render_metric_grid(REPORT_METRICS, columns=4)
    _render_table()
    _render_preview()

    render_shell_end()
