"""Purpose: Render the Alerts list and alert-detail workflow.

Repurposes the former mock "Investigations" page to show real alerts (the
Step 4 schema). Case management gets its own wiring in a later step; the
Notes tab remains backed by mock data until then.
"""

from __future__ import annotations

import streamlit as st

from api_client import alerts as alerts_api
from api_client import ai as ai_api
from api_client import cases as cases_api
from api_client.http import ApiClientError
from backend.security.rbac import Permission
from db.models.enums import AlertStatusEnum, SeverityEnum

from ..components import api_state
from ..components.layout import (
    ALERT_STATUS_DISPLAY,
    ALERT_STATUS_FROM_DISPLAY,
    render_bullet_list,
    render_data_table,
    render_html_block,
    render_timeline,
    severity_badge,
    status_badge,
)
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import INVESTIGATION_NOTES
from config.settings import AppConfig

SEVERITY_OPTIONS = ["All"] + [item.value for item in SeverityEnum]
STATUS_OPTIONS = ["All"] + [ALERT_STATUS_DISPLAY[item] for item in AlertStatusEnum]
PAGE_SIZE_OPTIONS = [10, 20, 50]


def _render_filters() -> dict:
    col_severity, col_status, col_host, col_user = st.columns(4)
    with col_severity:
        severity = st.selectbox("Severity", options=SEVERITY_OPTIONS, key="alerts_filter_severity")
    with col_status:
        status_label = st.selectbox("Status", options=STATUS_OPTIONS, key="alerts_filter_status")
    with col_host:
        hostname = st.text_input("Hostname", key="alerts_filter_hostname", placeholder="e.g. prod-bastion-01")
    with col_user:
        username = st.text_input("Username", key="alerts_filter_username", placeholder="e.g. admin")

    col_tactic, col_technique, col_page_size, _ = st.columns(4)
    with col_tactic:
        mitre_tactic = st.text_input("MITRE Tactic", key="alerts_filter_tactic", placeholder="e.g. Credential Access")
    with col_technique:
        mitre_technique_id = st.text_input("MITRE Technique ID", key="alerts_filter_technique", placeholder="e.g. T1110")
    with col_page_size:
        page_size = st.selectbox("Page Size", options=PAGE_SIZE_OPTIONS, index=1, key="alerts_filter_page_size")

    return {
        "severity": SeverityEnum(severity) if severity != "All" else None,
        "status": ALERT_STATUS_FROM_DISPLAY[status_label] if status_label != "All" else None,
        "hostname": hostname or None,
        "username": username or None,
        "mitre_tactic": mitre_tactic or None,
        "mitre_technique_id": mitre_technique_id or None,
        "page_size": page_size,
    }


def _render_list() -> None:
    filters = _render_filters()

    if st.session_state.get("alerts_page_filters") != filters:
        st.session_state["alerts_page_filters"] = filters
        st.session_state["alerts_page"] = 1

    page = st.session_state.get("alerts_page", 1)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Alerts</div>')

        with api_state.loading("Loading alerts..."):
            try:
                result = alerts_api.list_alerts(
                    severity=filters["severity"],
                    status=filters["status"],
                    hostname=filters["hostname"],
                    username=filters["username"],
                    mitre_tactic=filters["mitre_tactic"],
                    mitre_technique_id=filters["mitre_technique_id"],
                    page=page,
                    page_size=filters["page_size"],
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
                return

        if not result.items:
            api_state.render_empty_state("No alerts match the current filters.")
            return

        rows = [
            {
                "id": str(alert.id),
                "title": alert.title,
                "severity": alert.severity.value.capitalize(),
                "status": ALERT_STATUS_DISPLAY[alert.status],
                "hostname": alert.hostname or "—",
                "username": alert.username or "—",
                "created": alert.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for alert in result.items
        ]
        render_data_table(
            columns=["ID", "Alert", "Severity", "Status", "Host", "User", "Created"],
            rows=rows,
            keys=["id", "title", "severity", "status", "hostname", "username", "created"],
            severity_key="severity",
            status_key="status",
            mono_keys=["id"],
            strong_keys=["title"],
        )

        col_prev, col_page_info, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("← Prev", key="alerts_prev_page", disabled=page <= 1):
                st.session_state["alerts_page"] = page - 1
                st.rerun()
        with col_page_info:
            st.markdown(
                f'<div style="text-align:center; color:var(--text-secondary); padding-top:0.4rem;">'
                f"Page {result.page} of {result.total_pages} · {result.total} alerts</div>",
                unsafe_allow_html=True,
            )
        with col_next:
            if st.button("Next →", key="alerts_next_page", disabled=page >= result.total_pages):
                st.session_state["alerts_page"] = page + 1
                st.rerun()

        st.markdown("##### Open an alert")
        selected = st.selectbox(
            "Select an alert to view details",
            options=[alert.id for alert in result.items],
            format_func=lambda alert_id: next(
                f"#{a.id} — {a.title}" for a in result.items if a.id == alert_id
            ),
            key="alert_selector",
            label_visibility="collapsed",
        )
        if st.button("View Alert", type="primary", key="open_alert"):
            st.session_state["selected_alert"] = selected


def _render_detail(alert_id: int) -> None:
    with api_state.loading("Loading alert..."):
        try:
            alert = alerts_api.get_alert(alert_id, client=api_state.get_client())
        except ApiClientError as error:
            if st.button("← Back to Alerts", key="back_to_alerts_error"):
                st.session_state.pop("selected_alert", None)
                st.rerun()
            api_state.render_error(error)
            return

    if st.button("← Back to Alerts", key="back_to_alerts"):
        st.session_state.pop("selected_alert", None)
        st.rerun()

    render_html_block(
        f"""
        <div class="soc-section-card" style="margin-top:0.9rem;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.8rem;">
            <div>
              <div class="soc-card-label">#{alert.id}</div>
              <h3 class="soc-card-title" style="font-size:1.3rem;">{alert.title}</h3>
            </div>
            <div style="display:flex; gap:0.6rem;">{severity_badge(alert.severity.value.capitalize())}{status_badge(ALERT_STATUS_DISPLAY[alert.status])}</div>
          </div>
          <div class="soc-inline-list" style="margin-top:1rem;">
            <span><strong style="color:var(--text-primary);">Created:</strong> {alert.created_at.strftime('%Y-%m-%d %H:%M')}</span>
            <span><strong style="color:var(--text-primary);">Source:</strong> {alert.source or '—'}</span>
            <span><strong style="color:var(--text-primary);">Affected Host:</strong> <span class="soc-mono">{alert.hostname or '—'}</span></span>
            <span><strong style="color:var(--text-primary);">Affected User:</strong> <span class="soc-mono">{alert.username or '—'}</span></span>
          </div>
        </div>
        """
    )

    can_mutate = api_state.has_permission(Permission.MUTATE_INVESTIGATIONS)
    col_status, col_escalate = st.columns([3, 1])
    with col_status:
        status_options = [ALERT_STATUS_DISPLAY[item] for item in AlertStatusEnum]
        selected_status_label = st.selectbox(
            "Status",
            options=status_options,
            index=status_options.index(ALERT_STATUS_DISPLAY[alert.status]),
            key=f"status_select_{alert.id}",
            disabled=not can_mutate,
        )
        if can_mutate and st.button(
            "Update Status", type="primary", key=f"update_status_{alert.id}"
        ):
            try:
                alerts_api.update_alert(
                    alert.id,
                    status=ALERT_STATUS_FROM_DISPLAY[selected_status_label],
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.cache_data.clear()
                st.rerun()
    with col_escalate:
        st.markdown('<div style="margin-top:1.75rem;"></div>', unsafe_allow_html=True)
        if can_mutate and st.button("Escalate to Case", key=f"escalate_to_case_{alert.id}"):
            try:
                new_case = cases_api.create_case(
                    title=f"Investigate: {alert.title}",
                    alert_ids=[alert.id],
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.cache_data.clear()
                st.session_state.pop("selected_alert", None)
                st.session_state["selected_case"] = new_case.id
                st.session_state["selected_page"] = "Cases"
                st.success(f"Created case {new_case.case_number}. Opening in Cases…")
                st.rerun()

    _render_ai_triage(alert)

    tab_overview, tab_timeline, tab_evidence, tab_mitre, tab_notes = st.tabs(
        ["Overview", "Timeline", "Evidence", "MITRE", "Notes"]
    )

    with tab_overview:
        with st.container(border=True):
            render_html_block(
                f'<p class="soc-note">{alert.description or "No description recorded for this alert."}</p>'
            )

    with api_state.loading("Loading alert events..."):
        try:
            events = alerts_api.get_alert_events(alert.id, client=api_state.get_client())
        except ApiClientError as error:
            with tab_timeline:
                api_state.render_error(error)
            with tab_evidence:
                api_state.render_error(error)
            events = None

    if events is not None:
        with tab_timeline:
            with st.container(border=True):
                if not events.items:
                    api_state.render_empty_state("No events linked to this alert.")
                else:
                    timeline_items = [
                        {
                            "time": event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "event": event.event_category or event.event_action or event.source,
                            "detail": event.message or "",
                        }
                        for event in sorted(events.items, key=lambda event: event.timestamp)
                    ]
                    render_timeline(timeline_items)

        with tab_evidence:
            with st.container(border=True):
                if not events.items:
                    api_state.render_empty_state("No events linked to this alert.")
                else:
                    evidence_rows = [
                        {
                            "timestamp": event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                            "event_type": event.event_category or "—",
                            "source": event.source,
                            "evidence": event.message or "—",
                        }
                        for event in sorted(events.items, key=lambda event: event.timestamp)
                    ]
                    render_data_table(
                        columns=["Timestamp", "Event Type", "Source", "Evidence"],
                        rows=evidence_rows,
                        keys=["timestamp", "event_type", "source", "evidence"],
                        mono_keys=["timestamp"],
                    )

    with tab_mitre:
        with st.container(border=True):
            if alert.mitre_technique_id:
                render_bullet_list(
                    [
                        f"{alert.mitre_technique_id} — {alert.mitre_technique_name or 'Unknown Technique'}"
                        f" ({alert.mitre_tactic or 'Unknown Tactic'})"
                    ]
                )
            else:
                api_state.render_empty_state("No MITRE ATT&CK mapping recorded for this alert.")

    with tab_notes:
        with st.container(border=True):
            render_html_block('<div class="soc-card-label">NOTES · MOCK/DEMO DATA</div>')
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
            if can_mutate:
                st.text_area("Add a note", key="investigation_note_input", placeholder="Document findings, decisions, or next steps...")
                st.button("Add Note", type="primary", key="add_investigation_note")


def _render_ai_triage(alert) -> None:  # noqa: ANN001
    """Render explicit advisory triage, history, citations, and feedback."""
    with st.container(border=True):
        st.subheader("AI analyst assistance")
        st.caption("Advisory only. Deterministic alert evidence remains authoritative.")
        can_request = api_state.has_permission(Permission.REQUEST_AI)
        if can_request and st.button("Analyze with AI", type="primary", key=f"analyze_with_ai_{alert.id}", icon=":material/auto_awesome:"):
            with api_state.loading("Analyzing linked evidence..."):
                try:
                    analysis = ai_api.request_triage(alert.id, client=api_state.get_client())
                except ApiClientError as error:
                    api_state.render_error(error)
                else:
                    st.session_state[f"ai_analysis_{alert.id}"] = analysis
                    st.rerun()

        try:
            history = ai_api.get_triage_history(alert.id, client=api_state.get_client())
        except ApiClientError as error:
            api_state.render_error(error)
            return
        analysis = st.session_state.get(f"ai_analysis_{alert.id}")
        if analysis is None and history.items:
            analysis = history.items[-1]
        if analysis is None:
            if can_request:
                st.info("No AI analysis requested yet. Select Analyze with AI to run an advisory review.")
            else:
                st.info("No AI analysis exists. Your role can view results but cannot request one.")
            return
        if analysis.status == "unavailable":
            st.warning(analysis.error_message or "AI assistance is unavailable or unconfigured.")
            return
        if analysis.status != "succeeded" or not analysis.output:
            st.error(analysis.error_message or "AI analysis failed safely; deterministic workflows are unaffected.")
            return

        output = analysis.output
        st.markdown("#### Observed facts")
        facts = output.get("observed_facts", [])
        if not facts:
            st.info("No observed facts were returned.")
        for fact in facts:
            st.write(f"- {fact.get('claim', '')}")
            st.caption("Evidence: " + ", ".join(fact.get("evidence_ids", [])))
        st.markdown("#### Assessment / hypotheses")
        st.write(output.get("assessment", "No assessment returned."))
        st.metric("Confidence", f"{float(output.get('confidence', 0)):.0%}")
        for label, key in (("Missing information", "missing_information"), ("Next steps", "next_steps")):
            st.markdown(f"#### {label}")
            values = output.get(key, [])
            st.write("\n".join(f"- {value}" for value in values) if values else "None recorded.")
        st.caption("Evidence references: " + ", ".join(analysis.evidence_refs or []))
        st.caption(f"Analysis history: {history.total} attempt(s)")
        feedback = st.selectbox(
            "Analyst feedback",
            ["No feedback", "Helpful", "Needs correction"],
            key=f"ai_feedback_{alert.id}",
        )
        if feedback != "No feedback":
            st.caption("Feedback is recorded for this session only until feedback persistence is added.")


def render(config: AppConfig) -> None:
    """Render the Investigations (Alerts) page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Investigations",
        description="Triage and track real-time security alerts from one workspace.",
        breadcrumb="SOC workspace / investigations",
        status_chips=[],
    )

    selected_id = st.session_state.get("selected_alert")
    if selected_id:
        _render_detail(selected_id)
    else:
        _render_list()

    render_shell_end()
