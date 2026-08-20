"""Purpose: Render the Cases list, case-detail, and case-creation workflow."""

from __future__ import annotations

import streamlit as st

from api_client import cases as cases_api
from api_client.http import ApiClientError
from db.models.enums import CasePriorityEnum, CaseStatusEnum

from ..components import api_state
from ..components.layout import (
    ALERT_STATUS_DISPLAY,
    CASE_STATUS_DISPLAY,
    CASE_STATUS_FROM_DISPLAY,
    render_data_table,
    render_html_block,
    render_timeline,
    severity_badge,
    status_badge,
)
from ..components.theme import render_shell_end, render_shell_start
from config.settings import AppConfig

PRIORITY_OPTIONS = ["All"] + [item.value for item in CasePriorityEnum]
STATUS_OPTIONS = ["All"] + [CASE_STATUS_DISPLAY[item] for item in CaseStatusEnum]
PAGE_SIZE_OPTIONS = [10, 20, 50]


def _render_filters() -> dict:
    col_status, col_priority, col_assignee, col_page_size = st.columns(4)
    with col_status:
        status_label = st.selectbox("Status", options=STATUS_OPTIONS, key="cases_filter_status")
    with col_priority:
        priority = st.selectbox("Priority", options=PRIORITY_OPTIONS, key="cases_filter_priority")
    with col_assignee:
        assignee = st.text_input("Assignee", key="cases_filter_assignee", placeholder="e.g. jdoe")
    with col_page_size:
        page_size = st.selectbox("Page Size", options=PAGE_SIZE_OPTIONS, index=1, key="cases_filter_page_size")

    return {
        "status": CASE_STATUS_FROM_DISPLAY[status_label] if status_label != "All" else None,
        "priority": CasePriorityEnum(priority) if priority != "All" else None,
        "assignee": assignee or None,
        "page_size": page_size,
    }


def _render_create_form() -> None:
    with st.expander("Create Case"):
        with st.form("create_case_form"):
            title = st.text_input("Title", key="new_case_title")
            description = st.text_area("Description", key="new_case_description")
            col_priority, col_assignee = st.columns(2)
            with col_priority:
                priority_label = st.selectbox(
                    "Priority",
                    options=[item.value for item in CasePriorityEnum],
                    index=[item.value for item in CasePriorityEnum].index(CasePriorityEnum.MEDIUM.value),
                    key="new_case_priority",
                )
            with col_assignee:
                assignee = st.text_input("Assignee", key="new_case_assignee")
            submitted = st.form_submit_button("Create Case", type="primary")

        if submitted:
            if not title:
                st.error("Title is required.")
                return
            try:
                created = cases_api.create_case(
                    title=title,
                    description=description or None,
                    priority=CasePriorityEnum(priority_label),
                    assignee=assignee or None,
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.cache_data.clear()
                st.session_state["selected_case"] = created.id
                st.rerun()


def _render_list() -> None:
    filters = _render_filters()
    _render_create_form()

    if st.session_state.get("cases_page_filters") != filters:
        st.session_state["cases_page_filters"] = filters
        st.session_state["cases_page"] = 1

    page = st.session_state.get("cases_page", 1)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Cases</div>')

        with api_state.loading("Loading cases..."):
            try:
                result = cases_api.list_cases(
                    status=filters["status"],
                    priority=filters["priority"],
                    assignee=filters["assignee"],
                    page=page,
                    page_size=filters["page_size"],
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
                return

        if not result.items:
            api_state.render_empty_state("No cases match the current filters.")
            return

        rows = [
            {
                "case_number": case.case_number,
                "title": case.title,
                "priority": case.priority.value.capitalize(),
                "status": CASE_STATUS_DISPLAY[case.status],
                "assignee": case.assignee or "—",
                "created": case.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for case in result.items
        ]
        render_data_table(
            columns=["Case #", "Title", "Priority", "Status", "Assignee", "Created"],
            rows=rows,
            keys=["case_number", "title", "priority", "status", "assignee", "created"],
            severity_key="priority",
            status_key="status",
            mono_keys=["case_number"],
            strong_keys=["title"],
        )

        col_prev, col_page_info, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button("← Prev", key="cases_prev_page", disabled=page <= 1):
                st.session_state["cases_page"] = page - 1
                st.rerun()
        with col_page_info:
            st.markdown(
                f'<div style="text-align:center; color:var(--text-secondary); padding-top:0.4rem;">'
                f"Page {result.page} of {result.total_pages} · {result.total} cases</div>",
                unsafe_allow_html=True,
            )
        with col_next:
            if st.button("Next →", key="cases_next_page", disabled=page >= result.total_pages):
                st.session_state["cases_page"] = page + 1
                st.rerun()

        st.markdown("##### Open a case")
        selected = st.selectbox(
            "Select a case to view details",
            options=[case.id for case in result.items],
            format_func=lambda case_id: next(
                f"{c.case_number} — {c.title}" for c in result.items if c.id == case_id
            ),
            key="case_selector",
            label_visibility="collapsed",
        )
        if st.button("View Case", type="primary", key="open_case"):
            st.session_state["selected_case"] = selected


def _render_alerts_tab(case) -> None:
    with st.container(border=True):
        if not case.alerts:
            api_state.render_empty_state("No alerts linked to this case.")
        else:
            for alert in case.alerts:
                col_info, col_action = st.columns([5, 1])
                with col_info:
                    render_html_block(
                        f"""
                        <div class="soc-alert-row">
                          <div>
                            <div class="soc-alert-name">#{alert.id} — {alert.title}</div>
                            <div class="soc-alert-copy">{severity_badge(alert.severity.value.capitalize())} {status_badge(ALERT_STATUS_DISPLAY[alert.status])}</div>
                          </div>
                        </div>
                        """
                    )
                with col_action:
                    if st.button("Remove", key=f"remove_alert_{case.id}_{alert.id}"):
                        try:
                            cases_api.remove_case_alert(
                                case.id, alert.id, client=api_state.get_client()
                            )
                        except ApiClientError as error:
                            api_state.render_error(error)
                        else:
                            st.cache_data.clear()
                            st.rerun()

        st.markdown("##### Add Alert")
        col_input, col_button = st.columns([3, 1])
        with col_input:
            alert_id_input = st.number_input(
                "Alert ID",
                min_value=1,
                step=1,
                key=f"add_alert_id_{case.id}",
                label_visibility="collapsed",
            )
        with col_button:
            if st.button("Add Alert", key=f"add_alert_button_{case.id}"):
                try:
                    cases_api.add_case_alerts(
                        case.id, [int(alert_id_input)], client=api_state.get_client()
                    )
                except ApiClientError as error:
                    api_state.render_error(error)
                else:
                    st.cache_data.clear()
                    st.rerun()


def _render_activity_tab(case) -> None:
    with st.container(border=True):
        with api_state.loading("Loading activity..."):
            try:
                activities = cases_api.list_case_activities(case.id, client=api_state.get_client())
            except ApiClientError as error:
                api_state.render_error(error)
                activities = None

        if activities is not None:
            if not activities.items:
                api_state.render_empty_state("No activity recorded for this case.")
            else:
                timeline_items = [
                    {
                        "time": activity.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        "event": f"{activity.activity_type} · {activity.author or 'Unknown'}",
                        "detail": activity.message,
                    }
                    for activity in activities.items
                ]
                render_timeline(timeline_items)

        st.text_area("Add a note", key=f"case_note_input_{case.id}", placeholder="Document findings, decisions, or next steps...")
        if st.button("Add Note", type="primary", key=f"add_case_note_{case.id}"):
            note = st.session_state.get(f"case_note_input_{case.id}", "")
            if not note:
                st.error("Note text is required.")
            else:
                try:
                    cases_api.create_case_activity(
                        case.id, message=note, client=api_state.get_client()
                    )
                except ApiClientError as error:
                    api_state.render_error(error)
                else:
                    st.cache_data.clear()
                    st.rerun()


def _render_detail(case_id: int) -> None:
    with api_state.loading("Loading case..."):
        try:
            case = cases_api.get_case(case_id, client=api_state.get_client())
        except ApiClientError as error:
            if st.button("← Back to Cases", key="back_to_cases_error"):
                st.session_state.pop("selected_case", None)
                st.rerun()
            api_state.render_error(error)
            return

    if st.button("← Back to Cases", key="back_to_cases"):
        st.session_state.pop("selected_case", None)
        st.rerun()

    render_html_block(
        f"""
        <div class="soc-section-card" style="margin-top:0.9rem;">
          <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:0.8rem;">
            <div>
              <div class="soc-card-label">{case.case_number}</div>
              <h3 class="soc-card-title" style="font-size:1.3rem;">{case.title}</h3>
            </div>
            <div style="display:flex; gap:0.6rem;">{severity_badge(case.priority.value.capitalize())}{status_badge(CASE_STATUS_DISPLAY[case.status])}</div>
          </div>
          <div class="soc-inline-list" style="margin-top:1rem;">
            <span><strong style="color:var(--text-primary);">Created:</strong> {case.created_at.strftime('%Y-%m-%d %H:%M')}</span>
            <span><strong style="color:var(--text-primary);">Assignee:</strong> {case.assignee or '—'}</span>
          </div>
        </div>
        """
    )

    col_status, col_priority, col_button = st.columns([2, 2, 1])
    with col_status:
        status_options = [CASE_STATUS_DISPLAY[item] for item in CaseStatusEnum]
        selected_status_label = st.selectbox(
            "Status",
            options=status_options,
            index=status_options.index(CASE_STATUS_DISPLAY[case.status]),
            key=f"case_status_select_{case.id}",
        )
    with col_priority:
        priority_options = [item.value for item in CasePriorityEnum]
        selected_priority = st.selectbox(
            "Priority",
            options=priority_options,
            index=priority_options.index(case.priority.value),
            key=f"case_priority_select_{case.id}",
        )
    with col_button:
        st.markdown('<div style="margin-top:1.75rem;"></div>', unsafe_allow_html=True)
        if st.button("Update", type="primary", key=f"update_case_{case.id}"):
            try:
                cases_api.update_case(
                    case.id,
                    status=CASE_STATUS_FROM_DISPLAY[selected_status_label],
                    priority=CasePriorityEnum(selected_priority),
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.cache_data.clear()
                st.rerun()

    tab_alerts, tab_activity = st.tabs(["Alerts", "Activity"])
    with tab_alerts:
        _render_alerts_tab(case)
    with tab_activity:
        _render_activity_tab(case)


def render(config: AppConfig) -> None:
    """Render the Cases page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Cases",
        description="Manage investigation cases, linked alerts, and activity timelines.",
        breadcrumb="SOC workspace / cases",
        status_chips=[],
    )

    selected_id = st.session_state.get("selected_case")
    if selected_id:
        _render_detail(selected_id)
    else:
        _render_list()

    render_shell_end()
