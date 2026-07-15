"""Purpose: Define shared presentation helpers for Streamlit pages."""

from __future__ import annotations

from typing import Iterable

import streamlit as st

from backend.models.dashboard import DashboardMetric


def render_page_header(title: str, description: str) -> None:
    """Render a consistent page heading block.

    Args:
        title: Main page title.
        description: Supporting page description.
    """
    st.title(title)
    st.caption(description)


def render_metric_cards(metrics: Iterable[DashboardMetric]) -> None:
    """Display dashboard metrics in a compact card layout.

    Args:
        metrics: Metrics to render.
    """
    metric_list = list(metrics)
    columns = st.columns(len(metric_list))
    for column, metric in zip(columns, metric_list):
        column.metric(label=metric.label, value=metric.value, delta=metric.delta)


def render_placeholder_notice(title: str, body: str) -> None:
    """Display a clearly marked placeholder section.

    Args:
        title: Notice heading.
        body: Supporting explanation.
    """
    st.info(f"**{title}**\n\n{body}")
