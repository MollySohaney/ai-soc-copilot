"""Purpose: Render the MITRE ATT&CK exploration page."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_bullet_list, render_data_table, render_html_block
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import MITRE_TACTICS, MITRE_TECHNIQUES
from config.settings import AppConfig


def _technique_lookup() -> dict[str, dict]:
    return {item["id"]: item for item in MITRE_TECHNIQUES}


def render(config: AppConfig) -> None:
    """Render the MITRE ATT&CK explorer page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="MITRE ATT&CK",
        description="Explore adversary tactics and techniques associated with security activity.",
        breadcrumb="SOC workspace / mitre",
        status_chips=[("Framework", "ATT&CK v15 (mock)")],
    )

    search = st.text_input(
        "Search",
        placeholder="Search techniques, tactics, or IDs...",
        key="mitre_search",
        label_visibility="collapsed",
    )

    selected_tactic = st.session_state.get("mitre_selected_tactic", "All")
    render_html_block('<div class="soc-card-label" style="margin-top:0.9rem;">TACTICS</div>')
    tactic_cols = st.columns(5)
    for index, tactic in enumerate(["All"] + MITRE_TACTICS):
        with tactic_cols[index % 5]:
            if st.button(
                tactic,
                key=f"tactic_{tactic}",
                use_container_width=True,
                type="primary" if selected_tactic == tactic else "secondary",
            ):
                st.session_state["mitre_selected_tactic"] = tactic
                selected_tactic = tactic

    techniques = MITRE_TECHNIQUES
    if selected_tactic != "All":
        techniques = [t for t in techniques if selected_tactic in t["tactics"]]
    if search:
        needle = search.lower()
        techniques = [
            t for t in techniques
            if needle in t["id"].lower() or needle in t["name"].lower() or any(needle in tac.lower() for tac in t["tactics"])
        ]

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Techniques</div>')
        if techniques:
            render_data_table(
                columns=["ID", "Technique", "Tactic(s)"],
                rows=[{"id": t["id"], "name": t["name"], "tactics": ", ".join(t["tactics"])} for t in techniques],
                keys=["id", "name", "tactics"],
                mono_keys=["id"],
                strong_keys=["name"],
            )
        else:
            render_html_block('<div class="soc-note">No techniques match this search.</div>')

    st.markdown("##### Inspect a technique")
    selected_technique_id = st.selectbox(
        "Select a technique",
        options=[t["id"] for t in techniques] or [t["id"] for t in MITRE_TECHNIQUES],
        format_func=lambda tid: f"{tid} — {_technique_lookup()[tid]['name']}",
        key="mitre_technique_selector",
        label_visibility="collapsed",
    )

    technique = _technique_lookup()[selected_technique_id]
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block(
            f"""
            <div class="soc-card-label">TECHNIQUE DETAILS</div>
            <h3 class="soc-card-title" style="font-size:1.25rem;">
              <span class="soc-mono">{technique['id']}</span> — {technique['name']}
            </h3>
            <div class="soc-card-label" style="margin-top:1rem;">TACTIC</div>
            <div style="color:var(--text-primary); font-weight:600;">{" / ".join(technique['tactics'])}</div>
            <div class="soc-card-label" style="margin-top:1rem;">DESCRIPTION</div>
            <p class="soc-note">{technique['description']}</p>
            <div class="soc-inline-list" style="margin-top:0.6rem;">
              <span><strong style="color:var(--text-primary);">Observed in:</strong> {technique['observed_in']} alerts</span>
              <span><strong style="color:var(--text-primary);">Related investigations:</strong> {technique['related_investigations']}</span>
            </div>
            <div class="soc-card-label" style="margin-top:1rem;">DETECTION IDEAS</div>
            """
        )
        render_bullet_list(technique["detections"])

    render_shell_end()
