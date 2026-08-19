"""Purpose: Render the Analyze Alert upload/paste workflow and mock AI analysis results."""

from __future__ import annotations

import streamlit as st

from ..components.layout import (
    render_checklist,
    render_bullet_list,
    render_html_block,
    render_ioc_chips,
    render_risk_gauge,
)
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import ANALYSIS_RESULT, PLATFORM_OPTIONS, SAMPLE_ALERT_JSON
from backend.services.upload_service import AlertUploadService
from config.settings import AppConfig


def _render_upload_tab(config: AppConfig, upload_service: AlertUploadService) -> None:
    with st.container(border=True):
        render_html_block(
            """
            <div style="text-align:center; padding:1.4rem 1rem;">
              <div style="font-size:1.05rem; font-weight:700; color:var(--text-primary);">
                Drop a security alert here
              </div>
              <div style="color:var(--text-secondary); font-size:0.88rem; margin-top:0.4rem;">
                Supports JSON, CSV, TXT
              </div>
            </div>
            """
        )
        uploaded_file = st.file_uploader(
            label="Choose File",
            type=config.allowed_upload_types,
            help=f"Max file size: {config.max_upload_size_mb} MB",
            key="analyze_upload",
        )
        st.caption(f"Max file size: {config.max_upload_size_mb} MB")

        if uploaded_file is None:
            return

        result = upload_service.process_upload(file_name=uploaded_file.name, content=uploaded_file.getvalue())
        if not result.is_valid:
            st.error(result.message)
            return

        st.success(result.message)
        if st.button("Analyze Alert", type="primary", key="analyze_from_upload"):
            st.session_state["analysis_ready"] = True


def _render_paste_tab() -> None:
    with st.container(border=True):
        render_html_block('<div class="soc-card-label">Alert payload</div>')
        st.text_area(
            label="Paste alert JSON",
            value=SAMPLE_ALERT_JSON,
            height=220,
            key="analyze_paste_text",
            label_visibility="collapsed",
        )
        st.selectbox("Platform", options=PLATFORM_OPTIONS, index=0, key="analyze_platform")
        if st.button("Analyze Alert", type="primary", key="analyze_from_paste"):
            st.session_state["analysis_ready"] = True


def _render_analysis_results() -> None:
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">AI Analysis</div>')
        render_html_block(f'<p class="soc-note">{ANALYSIS_RESULT["summary"]}</p>')
        render_html_block(
            f"""
            <div class="soc-inline-list" style="margin-top:0.9rem;">
              <span><strong style="color:var(--text-primary);">Severity:</strong> {ANALYSIS_RESULT['severity']}</span>
              <span><strong style="color:var(--text-primary);">Confidence:</strong> {ANALYSIS_RESULT['confidence']}%</span>
              <span><strong style="color:var(--text-primary);">Category:</strong> {ANALYSIS_RESULT['category']}</span>
            </div>
            """
        )

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    col_risk, col_mitre = st.columns([1.75, 1])
    with col_risk:
        with st.container(border=True):
            render_html_block('<div class="soc-section-title">Risk Score</div>')
            render_risk_gauge(ANALYSIS_RESULT["risk_score"], ANALYSIS_RESULT["risk_label"])
            render_html_block('<div class="soc-card-label" style="margin-top:1.1rem;">RISK FACTORS</div>')
            render_bullet_list(ANALYSIS_RESULT["risk_factors"])
    with col_mitre:
        with st.container(border=True):
            mitre = ANALYSIS_RESULT["mitre"]
            render_html_block(
                f"""
                <div class="soc-section-title">MITRE ATT&amp;CK</div>
                <div class="soc-card-label">TACTIC</div>
                <div style="color:var(--text-primary); font-weight:600; margin-bottom:0.8rem;">{mitre['tactic']}</div>
                <div class="soc-card-label">TECHNIQUE</div>
                <div class="soc-mono" style="font-size:0.98rem; margin-bottom:0.6rem;">{mitre['technique_id']} — {mitre['technique']} ↗</div>
                <div class="soc-card-label">SUB-TECHNIQUE</div>
                <div class="soc-mono" style="font-size:0.92rem;">{mitre['sub_technique_id']} — {mitre['sub_technique']} ↗</div>
                """
            )

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Indicators of Compromise</div>')
        render_ioc_chips(ANALYSIS_RESULT["iocs"])

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    col_checklist, col_fp = st.columns([1.75, 1])
    with col_checklist:
        with st.container(border=True):
            render_html_block('<div class="soc-section-title">Investigation Checklist</div>')
            render_checklist(ANALYSIS_RESULT["checklist"], key_prefix="analysis_checklist")
    with col_fp:
        with st.container(border=True):
            render_html_block('<div class="soc-section-title">False Positive Considerations</div>')
            render_bullet_list(ANALYSIS_RESULT["false_positives"])

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Recommended Response</div>')
        response_cols = st.columns(3)
        for col, (stage, actions) in zip(response_cols, ANALYSIS_RESULT["response"].items()):
            with col:
                render_html_block(f'<div class="soc-case-name">{stage}</div>')
                render_bullet_list(actions)

    st.markdown('<div style="margin-top:1.2rem;"></div>', unsafe_allow_html=True)
    action_cols = st.columns(4)
    with action_cols[0]:
        st.button("Start Investigation", type="primary", use_container_width=True, key="action_start_investigation")
    with action_cols[1]:
        st.button("Ask Copilot", use_container_width=True, key="action_ask_copilot")
    with action_cols[2]:
        st.button("Generate Report", use_container_width=True, key="action_generate_report")
    with action_cols[3]:
        st.button("Export Analysis", use_container_width=True, key="action_export_analysis")


def render(config: AppConfig, upload_service: AlertUploadService) -> None:
    """Render the Analyze Alert page.

    Args:
        config: Application configuration.
        upload_service: Service that handles upload validation and file preview parsing.
    """
    render_shell_start(
        title="Analyze Alert",
        description="Upload or paste a security alert for AI-assisted investigation.",
        breadcrumb="SOC workspace / analyze",
        status_chips=[("Local AI", "Mock Mode")],
    )

    tab_upload, tab_paste = st.tabs(["Upload File", "Paste Alert"])
    with tab_upload:
        _render_upload_tab(config, upload_service)
    with tab_paste:
        _render_paste_tab()

    if st.session_state.get("analysis_ready"):
        st.markdown('<div style="margin-top:1.4rem;"></div>', unsafe_allow_html=True)
        _render_analysis_results()

    render_shell_end()
