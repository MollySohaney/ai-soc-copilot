"""Purpose: Render the high-level dashboard experience."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_metric_cards, render_page_header
from backend.services.health_service import HealthService
from config.settings import AppConfig


def render(config: AppConfig, health_service: HealthService) -> None:
    """Render the dashboard page.

    Args:
        config: Application configuration.
        health_service: Service that provides dashboard summary data.
    """
    render_page_header(
        title="Dashboard",
        description=(
            "Operational overview for the AI SOC Copilot foundation. "
            "Metrics are currently scaffold data and can be replaced by live sources later."
        ),
    )

    metrics = health_service.get_dashboard_metrics()
    render_metric_cards(metrics)

    st.subheader("Platform Status")
    st.write(
        {
            "application": config.app_name,
            "environment": config.environment,
            "debug_mode": config.debug,
            "allowed_upload_types": config.allowed_upload_types,
        }
    )

    st.subheader("Roadmap Focus")
    st.markdown(
        "- Alert normalization and validation\n"
        "- Analyst workflow orchestration\n"
        "- Secure AI integration boundaries\n"
        "- Report generation and evidence capture"
    )
