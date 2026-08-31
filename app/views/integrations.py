"""Purpose: Render the Integrations catalog of supported and planned platforms."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_html_block, render_integration_cards
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import SIEM_INTEGRATIONS, TI_INTEGRATIONS
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the Integrations page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Integrations",
        description="Connect security platforms and threat intelligence services.",
        breadcrumb="SOC workspace / integrations",
        status_chips=[("Data source", "Mock/demo data"), ("Connected", "0")],
    )

    with st.container(border=True):
        render_html_block('<div class="soc-section-title">SIEM &amp; Security Platforms</div>')
        render_integration_cards(SIEM_INTEGRATIONS)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Threat Intelligence</div>')
        render_integration_cards(TI_INTEGRATIONS)
        ti_cols = st.columns(3)
        for index, source in enumerate(TI_INTEGRATIONS):
            with ti_cols[index]:
                st.button(f"Configure {source['name']}", use_container_width=True, key=f"configure_{source['name']}")

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block(
            """
            <div class="soc-section-title">File-Based Analysis</div>
            <div class="soc-integration-card" style="max-width:420px;">
              <div class="soc-integration-name">Manual Alert Upload</div>
              <div class="soc-integration-category">Supported: JSON, CSV, TXT</div>
              <div class="soc-integration-status available">Available</div>
            </div>
            """
        )

    render_shell_end()
