"""Purpose: Render the Threat Intelligence lookup and enrichment page."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_data_table, render_html_block, render_risk_gauge
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import (
    THREAT_INTEL_HISTORY,
    THREAT_INTEL_RESULT,
    THREAT_INTEL_SOURCES,
    THREAT_INTEL_TYPES,
)
from config.settings import AppConfig


def _render_search() -> None:
    with st.container(border=True):
        render_html_block('<div class="soc-card-label">IOC LOOKUP</div>')
        col_input, col_type, col_button = st.columns([3, 1.2, 1])
        with col_input:
            st.text_input(
                "Indicator",
                placeholder="Search IP, domain, URL, or file hash",
                key="ti_search_value",
                label_visibility="collapsed",
            )
        with col_type:
            st.selectbox("Type", options=THREAT_INTEL_TYPES, index=0, key="ti_search_type", label_visibility="collapsed")
        with col_button:
            st.button("Investigate", type="primary", use_container_width=True, key="ti_investigate")


def _render_result() -> None:
    result = THREAT_INTEL_RESULT
    reputation_class = "severity-critical" if result["reputation"] == "Malicious" else "severity-medium"

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    col_result, col_reputation = st.columns([1.75, 1])
    with col_result:
        with st.container(border=True):
            render_html_block(
                f"""
                <div class="soc-card-label">RESULT</div>
                <h3 class="soc-card-title" style="font-size:1.35rem;"><span class="soc-mono">{result['indicator']}</span></h3>
                <div class="soc-inline-list" style="margin-top:0.5rem;">
                  <span><strong style="color:var(--text-primary);">Type:</strong> {result['type']}</span>
                  <span class="soc-severity-badge {reputation_class}">{result['reputation']}</span>
                </div>
                <div class="soc-card-label" style="margin-top:1rem;">RISK</div>
                """
            )
            render_risk_gauge(result["risk_score"], result["reputation"].upper())

    with col_reputation:
        with st.container(border=True):
            render_html_block(
                f"""
                <div class="soc-section-title">Reputation Summary</div>
                <ul class="soc-list">
                  <li><span>Malicious Vendors</span><strong>{result['malicious_vendors']}</strong></li>
                  <li><span>Suspicious Vendors</span><strong>{result['suspicious_vendors']}</strong></li>
                  <li><span>Harmless</span><strong>{result['harmless_vendors']}</strong></li>
                  <li><span>Last Observed</span><strong>{result['last_observed']}</strong></li>
                </ul>
                """
            )

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block(
            f"""
            <div class="soc-section-title">Related Intelligence</div>
            <ul class="soc-list">
              <li><span>Country</span><strong>{result['country']}</strong></li>
              <li><span>ASN</span><strong>{result['asn']}</strong></li>
              <li><span>Organization</span><strong>{result['organization']}</strong></li>
              <li><span>Known Malware</span><strong style="text-align:right; max-width:60%;">{result['known_malware']}</strong></li>
              <li><span>Associated Domains</span><strong>{', '.join(result['associated_domains'])}</strong></li>
              <li><span>Related MITRE Techniques</span><strong style="text-align:right; max-width:60%;">{', '.join(result['related_techniques'])}</strong></li>
            </ul>
            """
        )


def _render_sources() -> None:
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Intelligence Sources</div>')
        cards = "".join(
            f"""
            <div class="soc-integration-card">
              <div class="soc-integration-name">{source['name']}</div>
              <div class="soc-integration-category">Threat Intelligence Feed</div>
              <div class="soc-integration-status {'soon' if source['status'] == 'Mock Data' else ''}">{source['status']}</div>
            </div>
            """
            for source in THREAT_INTEL_SOURCES
        )
        render_html_block(f'<div class="soc-integration-grid">{cards}</div>')


def _render_history() -> None:
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Historical Searches</div>')
        render_data_table(
            columns=["Indicator", "Type", "Risk", "Verdict", "Last Checked"],
            rows=[{**row, "risk": f"{row['risk']} / 100"} for row in THREAT_INTEL_HISTORY],
            keys=["indicator", "type", "risk", "verdict", "last_checked"],
            status_key=None,
            mono_keys=["indicator"],
        )


def render(config: AppConfig) -> None:
    """Render the Threat Intelligence page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Threat Intelligence",
        description="Investigate IP addresses, domains, hashes, and other indicators.",
        breadcrumb="SOC workspace / threat intel",
        status_chips=[("Enrichment", "Mock Mode")],
    )

    _render_search()
    _render_result()
    _render_sources()
    _render_history()

    render_shell_end()
