"""Purpose: Render the Settings page for AI, analysis, threat intel, and app preferences."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_html_block
from ..components.theme import render_shell_end, render_shell_start
from config.settings import AppConfig

ANALYSIS_TOGGLES = [
    ("auto_mitre", "Automatically map MITRE ATT&CK", "Attach tactic/technique mappings to every analyzed alert."),
    ("extract_iocs", "Extract IOCs", "Pull IP addresses, domains, hashes, and users into structured indicators."),
    ("generate_checklist", "Generate investigation checklist", "Produce a starting checklist of next investigative steps."),
    ("include_fp", "Include false-positive analysis", "Surface likely benign explanations for the alert."),
    ("include_containment", "Include containment recommendations", "Suggest immediate steps to limit impact."),
    ("include_remediation", "Include remediation recommendations", "Suggest longer-term fixes and hardening steps."),
]

DEFAULT_TOGGLE_STATE = {
    "auto_mitre": True,
    "extract_iocs": True,
    "generate_checklist": True,
    "include_fp": True,
    "include_containment": True,
    "include_remediation": False,
}


def _render_ai_configuration() -> None:
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">AI Configuration</div>')
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("AI Provider", options=["Ollama", "OpenAI (coming soon)", "Anthropic (coming soon)"], index=0, key="settings_ai_provider")
            st.text_input("Model", value="llama3.1:8b", key="settings_ai_model")
        with col2:
            st.text_input("Ollama Endpoint", value="http://localhost:11434", key="settings_ollama_endpoint")
            render_html_block('<div class="soc-status-dot mock" style="margin-top:0.6rem;">Not Connected / Mock Mode</div>')
        st.button("Test Connection", key="settings_test_connection")


def _render_analysis_preferences() -> None:
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Analysis Preferences</div>')
        for key, label, copy in ANALYSIS_TOGGLES:
            col_label, col_toggle = st.columns([5, 1])
            with col_label:
                render_html_block(
                    f'<div class="soc-toggle-row-label">{label}</div><div class="soc-toggle-row-copy">{copy}</div>'
                )
            with col_toggle:
                st.toggle(label, value=DEFAULT_TOGGLE_STATE[key], key=f"settings_toggle_{key}", label_visibility="collapsed")


def _render_threat_intel_keys() -> None:
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Threat Intelligence</div>')
        st.text_input("VirusTotal API Key", type="password", placeholder="Not configured", key="settings_vt_key")
        st.text_input("AbuseIPDB API Key", type="password", placeholder="Not configured", key="settings_abuseipdb_key")
        st.text_input("AlienVault OTX API Key", type="password", placeholder="Not configured", key="settings_otx_key")
        render_html_block('<div class="soc-footer">Keys are never transmitted in this prototype. Connecting live threat-intel providers is planned for a future release.</div>')


def _render_app_preferences() -> None:
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Application Preferences</div>')
        col1, col2 = st.columns(2)
        with col1:
            st.selectbox("Theme", options=["Dark"], index=0, key="settings_theme")
            st.selectbox("Default Severity Threshold", options=["Low", "Medium", "High", "Critical"], index=1, key="settings_severity_threshold")
        with col2:
            st.selectbox(
                "Default Platform",
                options=["Auto Detect", "Elastic", "Splunk", "Microsoft Sentinel", "Wazuh", "CrowdStrike", "Microsoft Defender"],
                index=0,
                key="settings_default_platform",
            )
            st.selectbox("Report Format", options=["PDF", "DOCX", "Markdown"], index=0, key="settings_report_format")


def _render_privacy_panel() -> None:
    render_html_block(
        """
        <div class="soc-privacy-panel" style="margin-top:1rem;">
          <div class="soc-privacy-title">Local Processing</div>
          <p class="soc-note">
            When local AI is enabled, security alert data is intended to remain on the analyst's device
            unless an external threat-intelligence or AI provider is explicitly configured.
          </p>
        </div>
        """
    )


def render(config: AppConfig) -> None:
    """Render the Settings page.

    Args:
        config: Application configuration.
    """
    render_shell_start(
        title="Settings",
        description="Configure AI SOC Copilot preferences and local services.",
        breadcrumb="SOC workspace / settings",
        status_chips=[("Config source", "Local"), ("Environment", config.environment.upper())],
    )

    _render_ai_configuration()
    _render_analysis_preferences()
    _render_threat_intel_keys()
    _render_app_preferences()
    _render_privacy_panel()

    with st.expander("Runtime configuration (read-only, loaded at startup)"):
        st.json(config.to_safe_dict())

    render_shell_end()
