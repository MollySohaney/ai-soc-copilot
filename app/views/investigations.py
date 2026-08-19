"""Purpose: Render the Investigations list and case-detail workflow."""

from __future__ import annotations

import streamlit as st

from ..components.layout import (
    render_bullet_list,
    render_data_table,
    render_html_block,
    render_metric_grid,
    render_timeline,
    severity_badge,
    status_badge,
)
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import (
    INVESTIGATION_EVIDENCE,
    INVESTIGATION_METRICS,
    INVESTIGATION_NOTES,
    INVESTIGATION_OVERVIEW,
    INVESTIGATION_TIMELINE,
    INVESTIGATIONS,
)
from config.settings import AppConfig

STATUS_OPTIONS = ["New", "Investigating", "Contained", "Resolved"]


def _investigation_lookup() -> dict[str, dict]:
    return {item["id"]: item for item in INVESTIGATIONS}


def _render_list() -> None:
    render_metric_grid(INVESTIGATION_METRICS, columns=4)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Open Investigations</div>')
        render_data_table(
            columns=["ID", "Investigation", "Severity", "Status", "Assignee", "Alerts", "Created", "Last Updated"],
            rows=[{**item, "alerts": f"{item['alerts']} alerts"} for item in INVESTIGATIONS],
            keys=["id", "title", "severity", "status", "assignee", "alerts", "created", "updated"],
            severity_key="severity",
            status_key="status",
            mono_keys=["id"],
            strong_keys=["title"],
        )

    st.markdown("##### Open an investigation")
    selected = st.selectbox(
        "Select an investigation to view details",
        options=[item["id"] for item in INVESTIGATIONS],
        format_func=lambda inc_id: f"{inc_id} — {_investigation_lookup()[inc_id]['title']}",
        key="investigation_selector",
        label_visibility="collapsed",
    )
    if st.button("View Investigation", type="primary", key="open_investigation"):
        st.session_state["selected_investigation"] = selected


def _render_detail(investigation_id: str) -> None:
    case = _investigation_lookup().get(investigation_id)
    if case is None:
        st.session_state.pop("selected_investigation", None)
        return

    if st.button("← Back to Investigations", key="back_to_investigations"):
        st.session_state.pop("selected_investigation", None)
        st.rerun()

    render_html_block(
        f"""
        <div class="soc-section-card" style="margin-top:0.9rem;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.8rem;">
            <div>
              <div class="soc-card-label">{case['id']}</div>
              <h3 class="soc-card-title" style="font-size:1.3rem;">{case['title']}</h3>
            </div>
            <div style="display:flex; gap:0.6rem;">{severity_badge(case['severity'])}{status_badge(case['status'])}</div>
          </div>
          <div class="soc-inline-list" style="margin-top:1rem;">
            <span><strong style="color:var(--text-primary);">Created:</strong> {case['created']}</span>
            <span><strong style="color:var(--text-primary);">Assignee:</strong> {case['assignee']}</span>
            <span><strong style="color:var(--text-primary);">Source:</strong> {case['source']}</span>
            <span><strong style="color:var(--text-primary);">Affected Host:</strong> <span class="soc-mono">{case['host']}</span></span>
            <span><strong style="color:var(--text-primary);">Affected User:</strong> <span class="soc-mono">{case['user']}</span></span>
          </div>
        </div>
        """
    )

    st.selectbox("Status", options=STATUS_OPTIONS, index=STATUS_OPTIONS.index(case["status"]), key=f"status_select_{case['id']}")

    tab_overview, tab_timeline, tab_evidence, tab_mitre, tab_notes = st.tabs(
        ["Overview", "Timeline", "Evidence", "MITRE", "Notes"]
    )

    with tab_overview:
        with st.container(border=True):
            render_html_block(f'<p class="soc-note">{INVESTIGATION_OVERVIEW}</p>')

    with tab_timeline:
        with st.container(border=True):
            render_timeline(INVESTIGATION_TIMELINE)

    with tab_evidence:
        with st.container(border=True):
            render_data_table(
                columns=["Timestamp", "Event Type", "Source", "Evidence"],
                rows=INVESTIGATION_EVIDENCE,
                keys=["timestamp", "event_type", "source", "evidence"],
                mono_keys=["timestamp"],
            )

    with tab_mitre:
        with st.container(border=True):
            render_bullet_list(
                [
                    "T1110 — Brute Force (Credential Access)",
                    "T1110.001 — Password Guessing (Credential Access)",
                    "T1078 — Valid Accounts (Persistence, Privilege Escalation)",
                ]
            )

    with tab_notes:
        with st.container(border=True):
            for note in INVESTIGATION_NOTES:
                render_html_block(
                    f"""
                    <div class="soc-alert-row" style="margin-bottom:0.7rem;">
                      <div>
                        <div class="soc-alert-name">{note['author']} <span style="color:var(--text-muted); font-weight:400;">· {note['time']}</span></div>
                        <div class="soc-alert-copy">{note['note']}</div>
                      </div>
                    </div>
                    """
                )
            st.text_area("Add a note", key="investigation_note_input", placeholder="Document findings, decisions, or next steps...")
            st.button("Add Note", type="primary", key="add_investigation_note")


def render(config: AppConfig) -> None:
    """Render the Investigations page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Investigations",
        description="Track active security investigations and analyst workflows.",
        breadcrumb="SOC workspace / investigations",
        status_chips=[("Open", str(len(INVESTIGATIONS)))],
    )

    col_header, col_action = st.columns([4, 1])
    with col_action:
        st.button("New Investigation", type="primary", use_container_width=True, key="new_investigation_cta")

    selected_id = st.session_state.get("selected_investigation")
    if selected_id:
        _render_detail(selected_id)
    else:
        _render_list()

    render_shell_end()
