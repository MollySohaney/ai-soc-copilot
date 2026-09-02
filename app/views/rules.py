"""Purpose: Render the Detection Rules list, create, and edit workflow."""

from __future__ import annotations

import json

import streamlit as st

from api.schemas.detection_rule import MITRE_TACTICS
from api_client import rules as rules_api
from api_client.http import ApiClientError
from db.models.enums import SeverityEnum

from ..components import api_state
from ..components.layout import render_html_block, severity_badge, status_badge
from ..components.theme import render_shell_end, render_shell_start
from config.settings import AppConfig

ENABLED_OPTIONS = ["All", "Enabled", "Disabled"]
SEVERITY_OPTIONS = ["All"] + [item.value for item in SeverityEnum]
PAGE_SIZE_OPTIONS = [10, 20, 50]
LANGUAGE_OPTIONS = ["sigma", "kql", "spl", "yara", "custom"]
MITRE_TACTIC_OPTIONS = sorted(MITRE_TACTICS)
RULE_TYPE_OPTIONS = ["single", "threshold", "sequence"]


def _logic_from_text(value: str) -> dict | None:
    """Parse optional editor JSON and show a field-level error on failure."""
    if not value.strip():
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as error:
        st.error(f"Structured logic must be valid JSON (line {error.lineno}, column {error.colno}).")
        return None


def _render_filters() -> dict:
    col_enabled, col_severity, col_page_size, _ = st.columns(4)
    with col_enabled:
        enabled_label = st.selectbox("Enabled", options=ENABLED_OPTIONS, key="rules_filter_enabled")
    with col_severity:
        severity = st.selectbox("Severity", options=SEVERITY_OPTIONS, key="rules_filter_severity")
    with col_page_size:
        page_size = st.selectbox("Page Size", options=PAGE_SIZE_OPTIONS, index=1, key="rules_filter_page_size")

    enabled = None
    if enabled_label == "Enabled":
        enabled = True
    elif enabled_label == "Disabled":
        enabled = False

    return {
        "enabled": enabled,
        "severity": SeverityEnum(severity) if severity != "All" else None,
        "page_size": page_size,
    }


def _render_create_form() -> None:
    with st.expander("Create Rule"):
        with st.form("create_rule_form"):
            name = st.text_input("Name", key="new_rule_name")
            description = st.text_area("Description", key="new_rule_description")
            col_source, col_language = st.columns(2)
            with col_source:
                source = st.text_input("Source", key="new_rule_source")
            with col_language:
                language = st.selectbox("Language", options=LANGUAGE_OPTIONS, key="new_rule_language")
            query = st.text_area("Query", key="new_rule_query")
            rule_type = st.selectbox("Rule type", options=RULE_TYPE_OPTIONS, key="new_rule_type")
            structured_logic_text = st.text_area(
                "Structured logic (JSON, optional)", key="new_rule_logic",
                placeholder='{"rule_type":"single","condition":{"operator":"exists","field":"hostname"}}',
            )
            enabled_for_execution = st.checkbox("Enable for execution", key="new_rule_execution_enabled")
            col_severity, col_risk = st.columns(2)
            with col_severity:
                severity = st.selectbox(
                    "Severity", options=[item.value for item in SeverityEnum], key="new_rule_severity"
                )
            with col_risk:
                risk_score = st.number_input(
                    "Risk Score", min_value=0, max_value=100, value=50, step=1, key="new_rule_risk_score"
                )
            col_tactic, col_technique_id, col_technique_name = st.columns(3)
            with col_tactic:
                mitre_tactic = st.selectbox(
                    "MITRE Tactic", options=["(none)"] + MITRE_TACTIC_OPTIONS, key="new_rule_mitre_tactic"
                )
            with col_technique_id:
                mitre_technique_id = st.text_input(
                    "MITRE Technique ID", key="new_rule_mitre_technique_id", placeholder="e.g. T1110"
                )
            with col_technique_name:
                mitre_technique_name = st.text_input(
                    "MITRE Technique Name", key="new_rule_mitre_technique_name"
                )
            submitted = st.form_submit_button("Create Rule", type="primary")

        if submitted:
            if not name or not query:
                st.error("Name and query are required.")
                return
            structured_logic = _logic_from_text(structured_logic_text)
            if structured_logic_text.strip() and structured_logic is None:
                return
            try:
                rules_api.create_rule(
                    name=name,
                    query=query,
                    severity=SeverityEnum(severity),
                    language=language,
                    description=description or None,
                    source=source or None,
                    risk_score=int(risk_score),
                    mitre_tactic=mitre_tactic if mitre_tactic != "(none)" else None,
                    mitre_technique_id=mitre_technique_id or None,
                    mitre_technique_name=mitre_technique_name or None,
                    structured_logic=structured_logic,
                    rule_type=rule_type,
                    enabled_for_execution=enabled_for_execution,
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.cache_data.clear()
                st.rerun()


def _render_edit_form(rule) -> None:
    with st.expander(f"Edit {rule.name}"):
        with st.form(f"edit_rule_form_{rule.id}"):
            description = st.text_area("Description", value=rule.description or "", key=f"edit_rule_description_{rule.id}")
            col_source, col_language = st.columns(2)
            with col_source:
                source = st.text_input("Source", value=rule.source or "", key=f"edit_rule_source_{rule.id}")
            with col_language:
                language_index = LANGUAGE_OPTIONS.index(rule.language) if rule.language in LANGUAGE_OPTIONS else 0
                language = st.selectbox(
                    "Language", options=LANGUAGE_OPTIONS, index=language_index, key=f"edit_rule_language_{rule.id}"
                )
            query = st.text_area("Query", value=rule.query, key=f"edit_rule_query_{rule.id}")
            rule_type_index = RULE_TYPE_OPTIONS.index(rule.rule_type) if rule.rule_type in RULE_TYPE_OPTIONS else 0
            rule_type = st.selectbox("Rule type", options=RULE_TYPE_OPTIONS, index=rule_type_index, key=f"edit_rule_type_{rule.id}")
            structured_logic_text = st.text_area(
                "Structured logic (JSON)", value=json.dumps(rule.structured_logic or {}, indent=2),
                key=f"edit_rule_logic_{rule.id}",
            )
            enabled_for_execution = st.checkbox(
                "Enable for execution", value=rule.enabled_for_execution, key=f"edit_rule_execution_enabled_{rule.id}"
            )
            col_severity, col_risk = st.columns(2)
            with col_severity:
                severity_options = [item.value for item in SeverityEnum]
                severity = st.selectbox(
                    "Severity",
                    options=severity_options,
                    index=severity_options.index(rule.severity.value),
                    key=f"edit_rule_severity_{rule.id}",
                )
            with col_risk:
                risk_score = st.number_input(
                    "Risk Score",
                    min_value=0,
                    max_value=100,
                    value=rule.risk_score if rule.risk_score is not None else 0,
                    step=1,
                    key=f"edit_rule_risk_score_{rule.id}",
                )
            col_tactic, col_technique_id, col_technique_name = st.columns(3)
            with col_tactic:
                tactic_options = ["(none)"] + MITRE_TACTIC_OPTIONS
                tactic_index = tactic_options.index(rule.mitre_tactic) if rule.mitre_tactic in tactic_options else 0
                mitre_tactic = st.selectbox(
                    "MITRE Tactic", options=tactic_options, index=tactic_index, key=f"edit_rule_mitre_tactic_{rule.id}"
                )
            with col_technique_id:
                mitre_technique_id = st.text_input(
                    "MITRE Technique ID", value=rule.mitre_technique_id or "", key=f"edit_rule_mitre_technique_id_{rule.id}"
                )
            with col_technique_name:
                mitre_technique_name = st.text_input(
                    "MITRE Technique Name",
                    value=rule.mitre_technique_name or "",
                    key=f"edit_rule_mitre_technique_name_{rule.id}",
                )
            submitted = st.form_submit_button("Save Changes", type="primary")

        if submitted:
            structured_logic = _logic_from_text(structured_logic_text)
            if structured_logic_text.strip() and structured_logic is None:
                return
            try:
                rules_api.update_rule(
                    rule.id,
                    description=description or None,
                    source=source or None,
                    language=language,
                    query=query,
                    severity=SeverityEnum(severity),
                    risk_score=int(risk_score),
                    mitre_tactic=mitre_tactic if mitre_tactic != "(none)" else None,
                    mitre_technique_id=mitre_technique_id or None,
                    mitre_technique_name=mitre_technique_name or None,
                    structured_logic=structured_logic,
                    rule_type=rule_type,
                    enabled_for_execution=enabled_for_execution,
                    client=api_state.get_client(),
                )
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.cache_data.clear()
                st.rerun()


def _render_rule_row(rule) -> None:
    with st.container(border=True):
        col_info, col_toggle = st.columns([5, 1])
        with col_info:
            render_html_block(
                f"""
                <div class="soc-alert-row">
                  <div>
                    <div class="soc-alert-name">{rule.name}</div>
                    <div class="soc-alert-copy">
                      {severity_badge(rule.severity.value.capitalize())}
                      {status_badge('Enabled' if rule.enabled else 'Disabled')}
                      <span class="soc-mono">{rule.language or '—'}</span>
                      · {rule.source or '—'}
                      · {rule.mitre_tactic or '—'} {rule.mitre_technique_id or ''}
                    </div>
                  </div>
                </div>
                """
            )
        with col_toggle:
            toggle_label = "Disable" if rule.enabled else "Enable"
            if st.button(toggle_label, key=f"toggle_rule_{rule.id}"):
                try:
                    rules_api.update_rule(
                        rule.id, enabled=not rule.enabled, client=api_state.get_client()
                    )
                except ApiClientError as error:
                    api_state.render_error(error)
                else:
                    st.cache_data.clear()
                    st.rerun()

        _render_edit_form(rule)
        with st.expander("Test, run, and history"):
            col_test, col_run = st.columns(2)
            with col_test:
                if st.button("Test rule", key=f"test_rule_{rule.id}", icon=":material/science:"):
                    try:
                        result = rules_api.test_rule(rule.id, client=api_state.get_client())
                    except ApiClientError as error:
                        api_state.render_error(error)
                    else:
                        st.info(f"Dry run: {len(result.would_fire)} would-be firing(s); no alerts were created.")
                        for firing in result.would_fire:
                            _render_firing_explanation(firing)
            with col_run:
                confirmed = st.checkbox("Confirm run", key=f"confirm_rule_{rule.id}")
                if st.button("Run now", key=f"run_rule_{rule.id}", disabled=not confirmed, type="primary"):
                    try:
                        result = rules_api.execute_rule(rule.id, client=api_state.get_client())
                    except ApiClientError as error:
                        api_state.render_error(error)
                    else:
                        st.success(f"Run {result.status}: {len(result.alerts_created)} alert(s) created.")
                        st.cache_data.clear()
            try:
                history = rules_api.list_runs(rule.id, client=api_state.get_client())
            except ApiClientError as error:
                api_state.render_error(error)
            else:
                st.caption("Recent runs")
                for run in history.items:
                    st.write(f"{run.status} · {run.window_start.isoformat()} – {run.window_end.isoformat()} · {run.events_scanned} events · {run.alerts_created} alerts")


def _render_firing_explanation(firing: dict) -> None:
    """Render a dry-run firing as concise analyst-readable evidence."""
    evidence = firing.get("evidence_event_ids", [])
    if evidence:
        st.write(f"Matched evidence: {', '.join(evidence)}")
    for stage, event_ids in firing.get("stage_evidence", {}).items():
        st.write(f"Stage **{stage}**: {', '.join(event_ids)}")
    if firing.get("group"):
        st.write(f"Correlation group: {firing['group']}")
    if firing.get("correlation"):
        st.write(f"Correlation: {firing['correlation']}")
    if firing.get("explanation", {}).get("children"):
        st.caption(firing["explanation"]["children"])


def _render_list() -> None:
    filters = _render_filters()
    _render_create_form()

    if st.session_state.get("rules_page_filters") != filters:
        st.session_state["rules_page_filters"] = filters
        st.session_state["rules_page"] = 1

    page = st.session_state.get("rules_page", 1)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    render_html_block('<div class="soc-section-title">Detection Rules</div>')

    with api_state.loading("Loading detection rules..."):
        try:
            result = rules_api.list_rules(
                enabled=filters["enabled"],
                severity=filters["severity"],
                page=page,
                page_size=filters["page_size"],
                client=api_state.get_client(),
            )
        except ApiClientError as error:
            api_state.render_error(error)
            return

    if not result.items:
        api_state.render_empty_state("No detection rules match the current filters.")
        return

    for rule in result.items:
        _render_rule_row(rule)

    col_prev, col_page_info, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("← Prev", key="rules_prev_page", disabled=page <= 1):
            st.session_state["rules_page"] = page - 1
            st.rerun()
    with col_page_info:
        st.markdown(
            f'<div style="text-align:center; color:var(--text-secondary); padding-top:0.4rem;">'
            f"Page {result.page} of {result.total_pages} · {result.total} rules</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("Next →", key="rules_next_page", disabled=page >= result.total_pages):
            st.session_state["rules_page"] = page + 1
            st.rerun()


def render(config: AppConfig) -> None:
    """Render the Detection Rules page.

    Args:
        config: Application configuration.
    """
    _ = config
    render_shell_start(
        title="Detection Rules",
        description="Author and manage detection rules mapped to MITRE ATT&CK.",
        breadcrumb="SOC workspace / detection rules",
        status_chips=[],
    )

    _render_list()

    render_shell_end()
