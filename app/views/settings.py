"""Purpose: Render the settings and runtime configuration page."""

from __future__ import annotations

import streamlit as st

from ..components.theme import render_shell_end, render_shell_start
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the Settings page.

    Args:
        config: Application configuration.
    """
    render_shell_start(
        title="Settings",
        description="Read-only runtime configuration loaded during application startup.",
        breadcrumb="SOC workspace / settings",
        status_chips=[
            ("Config source", "Environment"),
            ("Access", "Read only"),
        ],
    )

    st.json(config.to_safe_dict())
    render_shell_end()
