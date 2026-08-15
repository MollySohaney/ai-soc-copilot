"""Purpose: Render the Security Overview dashboard experience."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from ..components.layout import (
    render_data_table,
    render_html_block,
    render_metric_grid,
)
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import (
    ALERT_ACTIVITY_SERIES,
    DASHBOARD_METRICS,
    MITRE_ACTIVITY,
    RECENT_ALERTS,
    SEVERITY_DISTRIBUTION,
)
from backend.services.health_service import HealthService
from config.settings import AppConfig

SEVERITY_COLORS = {
    "Critical": "#ff6b81",
    "High": "#ff8a48",
    "Medium": "#ffb648",
    "Low": "#36d399",
}


def _render_activity_chart() -> None:
    st.markdown(
        '<div class="soc-card-label" style="display:flex; justify-content:space-between; align-items:center;">'
        '<span>ALERT ACTIVITY</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<h3 class="soc-card-title">Alert Activity</h3>'
        '<p class="soc-card-subtitle">Security alerts over the last 7 days</p>',
        unsafe_allow_html=True,
    )
    st.segmented_control(
        "Range",
        options=["24H", "7D", "30D"],
        default="7D",
        key="dashboard_range",
        label_visibility="collapsed",
    )

    fig = go.Figure()
    for series_name in ["Critical", "High", "Medium", "Low"]:
        fig.add_trace(
            go.Scatter(
                x=ALERT_ACTIVITY_SERIES["days"],
                y=ALERT_ACTIVITY_SERIES[series_name],
                name=series_name,
                mode="lines",
                stackgroup="severity",
                line=dict(width=1.5, color=SEVERITY_COLORS[series_name]),
                fillcolor=_rgba(SEVERITY_COLORS[series_name], 0.28),
            )
        )
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#9aa9cf", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(showgrid=False, color="#7282a9"),
        yaxis=dict(showgrid=True, gridcolor="rgba(133,164,255,0.08)", color="#7282a9"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _render_severity_distribution() -> None:
    st.markdown(
        '<div class="soc-card-label">SEVERITY</div>'
        '<h3 class="soc-card-title">Severity Distribution</h3>',
        unsafe_allow_html=True,
    )
    total = sum(item["count"] for item in SEVERITY_DISTRIBUTION)
    fig = go.Figure(
        data=[
            go.Pie(
                labels=[item["severity"] for item in SEVERITY_DISTRIBUTION],
                values=[item["count"] for item in SEVERITY_DISTRIBUTION],
                hole=0.62,
                marker=dict(colors=[SEVERITY_COLORS[item["severity"]] for item in SEVERITY_DISTRIBUTION]),
                textinfo="none",
                sort=False,
            )
        ]
    )
    fig.update_layout(
        height=210,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        annotations=[dict(text=f"{total}<br><span style='font-size:11px;color:#7282a9'>Alerts</span>", x=0.5, y=0.5, showarrow=False, font=dict(color="#f4f7ff", size=22))],
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    rows = "".join(
        f"""
        <div class="soc-status-row">
          <span class="soc-status-dot" style="--dot-color:{SEVERITY_COLORS[item['severity']]}">
            <span style="display:inline-block;width:7px;height:7px;border-radius:999px;background:{SEVERITY_COLORS[item['severity']]};margin-right:0.4rem;"></span>
            {item['severity']}
          </span>
          <strong style="color:#f4f7ff;">{item['count']}</strong>
        </div>
        """
        for item in SEVERITY_DISTRIBUTION
    )
    render_html_block(rows)


def _render_mitre_activity() -> None:
    render_html_block('<div class="soc-card-label">MITRE ACTIVITY</div><h3 class="soc-card-title">Top Observed Techniques</h3>')
    max_count = max(item["count"] for item in MITRE_ACTIVITY)
    rows = "".join(
        f"""
        <div style="margin-bottom:0.8rem;">
          <div style="display:flex; justify-content:space-between; font-size:0.85rem; margin-bottom:0.3rem;">
            <span class="soc-mono" style="color:#c3d3ff;">{item['technique_id']}</span>
            <span style="color:#9aa9cf;">{item['name']} · {item['count']}</span>
          </div>
          <div class="soc-progress-bar" style="margin-top:0;">
            <span style="width:{int(item['count'] / max_count * 100)}%;"></span>
          </div>
        </div>
        """
        for item in MITRE_ACTIVITY
    )
    render_html_block(rows)


def render(config: AppConfig, health_service: HealthService) -> None:
    """Render the Security Overview dashboard page.

    Args:
        config: Application configuration.
        health_service: Service that provides dashboard summary data (reserved for future use).
    """
    _ = health_service
    render_shell_start(
        title="Security Overview",
        description="Monitor alerts, investigations, and threat activity from one workspace.",
        breadcrumb="SOC workspace / dashboard",
        status_chips=[("Environment", config.environment.upper())],
    )

    col_header, col_action = st.columns([4, 1])
    with col_action:
        st.button("Analyze New Alert", type="primary", use_container_width=True, key="dashboard_analyze_cta")

    render_metric_grid(DASHBOARD_METRICS, columns=4)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    col_chart, col_severity = st.columns([1.7, 0.95])
    with col_chart:
        with st.container(border=True):
            _render_activity_chart()
    with col_severity:
        with st.container(border=True):
            _render_severity_distribution()

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Recent Alerts</div>')
        render_data_table(
            columns=["Severity", "Alert", "Source", "Source IP", "User", "Timestamp", "Status"],
            rows=RECENT_ALERTS,
            keys=["severity", "alert", "source", "source_ip", "user", "timestamp", "status"],
            severity_key="severity",
            status_key="status",
            mono_keys=["source_ip"],
            strong_keys=["alert"],
        )

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        _render_mitre_activity()

    render_shell_end()
