"""Purpose: Render the Incident Reports listing and report preview."""

from __future__ import annotations

import streamlit as st

from api_client import ai as ai_api
from api_client import cases as cases_api
from ..components import api_state
from api_client.http import ApiClientError
from backend.security.rbac import Permission
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
        status_chips=[("Data source", "Mock/demo data"), ("Export target", "Local only")],
    )

    col_header, col_action = st.columns([4, 1])
    with col_action:
        if api_state.has_permission(Permission.REQUEST_AI) and st.button(
            "Generate report", type="primary", key="generate_report_cta"
        ):
            st.session_state["report_generation_requested"] = True

    with st.container(border=True):
        st.subheader("Evidence-grounded draft")
        st.caption("Drafts use confirmed content linked to one case. Recommendations are advisory only.")
        try:
            cases = cases_api.list_cases(page=1, page_size=100, client=api_state.get_client())
        except ApiClientError as error:
            api_state.render_error(error)
            cases = None
        if cases and cases.items:
            selected_case = st.selectbox(
                "Case",
                cases.items,
                format_func=lambda item: f"{item.case_number} — {item.title}",
                key="report_case_selector",
            )
            if api_state.has_permission(Permission.REQUEST_AI) and st.button(
                "Draft from confirmed case content", key="draft_case_report"
            ):
                try:
                    draft = ai_api.draft_report(selected_case.id, client=api_state.get_client())
                except ApiClientError as error:
                    api_state.render_error(error)
                else:
                    st.session_state["ai_report_draft"] = draft
            draft = st.session_state.get("ai_report_draft")
            if draft is not None:
                if draft.status == "succeeded" and draft.output:
                    st.markdown("#### Executive summary")
                    st.write(draft.output.get("executive_summary", ""))
                    st.markdown("#### Actions recorded")
                    st.json(draft.output.get("actions_recorded", []))
                    st.markdown("#### Recommendations")
                    st.write("\n".join(f"- {item}" for item in draft.output.get("recommendations", [])))
                    st.caption("Evidence references: " + ", ".join(draft.evidence_refs or []))
                elif draft.status == "unavailable":
                    st.warning(draft.error_message or "AI report drafting is unavailable.")
                else:
                    st.error(draft.error_message or "AI report drafting failed safely.")
        else:
            st.info("No cases are available for an evidence-grounded draft.")

    render_metric_grid(REPORT_METRICS, columns=4)
    _render_table()
    _render_preview()

    render_shell_end()
