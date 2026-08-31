"""Purpose: Render integration controls for telemetry sources and planned platforms."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from api_client import events as events_api
from api_client import ingestion as ingestion_api
from api_client.http import ApiClientError

from ..components import api_state
from ..components.layout import render_html_block, render_integration_cards
from ..components.theme import render_shell_end, render_shell_start
from ..data.mock_data import SIEM_INTEGRATIONS, TI_INTEGRATIONS
from config.settings import AppConfig

DEFAULT_START = "2026-08-15T02:00:00+00:00"
DEFAULT_END = "2026-08-15T04:00:00+00:00"


@st.cache_data(ttl=15)
def _load_ingestion_status():
    return ingestion_api.get_status(client=api_state.get_client())


@st.cache_data(ttl=15)
def _load_ingestion_runs():
    return ingestion_api.list_runs(page_size=5, client=api_state.get_client())


@st.cache_data(ttl=15)
def _load_recent_events():
    return events_api.list_events(page_size=100, client=api_state.get_client())


def render(config: AppConfig) -> None:
    """Render the Integrations page.

    Args:
        config: Application configuration.
    """
    connected_count = "1" if config.elastic_url else "0"
    render_shell_start(
        title="Integrations",
        description="Connect security platforms and threat intelligence services.",
        breadcrumb="SOC workspace / integrations",
        status_chips=[("Data source", "API-backed ingestion"), ("Connected", connected_count)],
    )

    _render_ingestion_controls(config)
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    _render_ingestion_status()
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    _render_recent_ingested_events()
    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)

    with st.container(border=True):
        render_html_block('<div class="soc-section-title">SIEM &amp; Security Platforms</div>')
        render_integration_cards(SIEM_INTEGRATIONS)

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Threat Intelligence</div>')
        render_integration_cards(TI_INTEGRATIONS)
        ti_cols = st.columns(3)
        for index, source in enumerate(TI_INTEGRATIONS):
            with ti_cols[index]:
                st.button(
                    f"Configure {source['name']}",
                    width="stretch",
                    key=f"configure_{source['name']}",
                )

    st.markdown('<div style="margin-top:1rem;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        render_html_block(
            """
            <div class="soc-section-title">File-Based Analysis</div>
            <div class="soc-integration-card" style="max-width:420px;">
              <div class="soc-integration-name">Manual Alert Upload</div>
              <div class="soc-integration-category">Supported: JSON, CSV, TXT</div>
              <div class="soc-integration-status available">Available</div>
            </div>
            """
        )

    render_shell_end()


def _render_ingestion_controls(config: AppConfig) -> None:
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Telemetry ingestion</div>')
        provider = st.segmented_control(
            "Provider",
            options=["fixture", "elastic"],
            default="fixture",
            key="ingestion_provider",
        )
        source_name = st.text_input(
            "Source name",
            value="fixture-default" if provider == "fixture" else "elastic-default",
            key=f"ingestion_source_name_{provider}",
        )

        with st.container(horizontal=True):
            if st.button("Test connection", icon=":material/cable:", key="test_ingestion"):
                _test_connection(provider, source_name)

        with st.form("manual_ingestion_sync", border=False):
            start_time = st.text_input("Start time", value=DEFAULT_START)
            end_time = st.text_input("End time", value=DEFAULT_END)
            limit = st.number_input(
                "Record limit",
                min_value=1,
                max_value=config.max_ingestion_sync_limit,
                value=min(100, config.max_ingestion_sync_limit),
                step=25,
            )
            dry_run = st.toggle("Dry run", value=True)
            submitted = st.form_submit_button("Run bounded sync", icon=":material/sync:")

        if submitted:
            _run_sync(
                provider=provider,
                source_name=source_name,
                start_time=start_time,
                end_time=end_time,
                limit=int(limit),
                dry_run=dry_run,
            )


def _test_connection(provider: str, source_name: str) -> None:
    try:
        result = ingestion_api.test_connection(
            provider,
            source_name=source_name or None,
            client=api_state.get_client(),
        )
    except ApiClientError as error:
        api_state.render_error(error)
        return
    if result.ok:
        st.success(result.message, icon=":material/check_circle:")
    else:
        st.warning(result.message, icon=":material/warning:")


def _run_sync(
    *,
    provider: str,
    source_name: str,
    start_time: str,
    end_time: str,
    limit: int,
    dry_run: bool,
) -> None:
    try:
        result = ingestion_api.sync_provider(
            provider,
            source_name=source_name or None,
            start_time=_parse_datetime(start_time),
            end_time=_parse_datetime(end_time),
            limit=limit,
            dry_run=dry_run,
            client=api_state.get_client(),
        )
    except ValueError:
        st.error("Enter valid ISO-8601 start and end times.", icon=":material/error:")
        return
    except ApiClientError as error:
        api_state.render_error(error)
        return

    st.cache_data.clear()
    st.success(
        (
            f"Run {result.run_id} {result.status}: "
            f"{result.persisted_count} persisted, {result.duplicate_count} duplicates, "
            f"{result.failed_count} failed."
        ),
        icon=":material/check_circle:",
    )


def _render_ingestion_status() -> None:
    with api_state.loading("Loading ingestion status..."):
        try:
            status = _load_ingestion_status()
            runs = _load_ingestion_runs()
        except ApiClientError as error:
            api_state.render_error(error)
            return

    latest = status.latest_run
    metrics = [
        ("Latest status", latest.status if latest else "No runs"),
        ("Persisted", str(latest.persisted_count if latest else 0)),
        ("Duplicates", str(latest.duplicate_count if latest else 0)),
        ("Checkpoints", str(len(status.checkpoints))),
    ]
    metric_markup = "".join(
        f"""
        <div class="soc-kpi-card">
          <div class="soc-kpi-label">{label}</div>
          <div class="soc-kpi-value">{value}</div>
        </div>
        """
        for label, value in metrics
    )
    with st.container(border=True):
        render_html_block(
            '<div class="soc-section-title">Ingestion status</div>'
            f'<div class="soc-kpi-grid">{metric_markup}</div>'
        )
        if runs.items:
            run_rows = [
                {
                    "run": str(run.id),
                    "provider": run.provider,
                    "source": run.source_name,
                    "status": run.status,
                    "fetched": str(run.fetched_count),
                    "persisted": str(run.persisted_count),
                    "failed": str(run.failed_count),
                }
                for run in runs.items
            ]
            st.dataframe(run_rows, hide_index=True)


def _render_recent_ingested_events() -> None:
    with api_state.loading("Loading recently ingested events..."):
        try:
            events = _load_recent_events()
        except ApiClientError as error:
            api_state.render_error(error)
            return

    ingested_events = [
        event for event in events.items if event.source_provider or event.raw_payload or event.raw_event
    ][:10]
    with st.container(border=True):
        render_html_block('<div class="soc-section-title">Recently ingested events</div>')
        if not ingested_events:
            api_state.render_empty_state("No ingested telemetry events found.")
            return

        rows = [
            {
                "id": event.id,
                "time": event.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "provider": event.source_provider or event.source,
                "source": event.source_instance or "—",
                "category": event.event_category or "—",
                "action": event.event_action or "—",
                "host": event.hostname or "—",
                "user": event.username or "—",
                "message": event.message or "—",
            }
            for event in ingested_events
        ]
        st.dataframe(rows, hide_index=True)

        selected_event_id = st.selectbox(
            "Raw evidence event",
            options=[event.id for event in ingested_events],
            format_func=lambda event_id: f"Event {event_id}",
        )
        selected = next(event for event in ingested_events if event.id == selected_event_id)
        with st.expander("Raw source evidence"):
            st.json(_raw_evidence(selected))


def _raw_evidence(event: Any) -> dict[str, Any]:
    return event.raw_payload or event.raw_event or {}


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
