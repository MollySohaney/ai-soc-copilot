"""Purpose: Render the settings and runtime configuration page."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_page_header
from config.settings import AppConfig


def render(config: AppConfig) -> None:
    """Render the Settings page.

    Args:
        config: Application configuration.
    """
    render_page_header(
        title="Settings",
        description="Read-only runtime settings loaded during application startup.",
    )

    st.json(config.to_safe_dict())
