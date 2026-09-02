"""Purpose: Verify the Investigations (Alerts) page against real seeded data via AppTest.

Script-runs `app/views/investigations.py`'s `render()` through Streamlit's
`AppTest`, with `api_state.get_client` monkeypatched to the seeded
in-memory API (`api_client_transport`), so assertions exercise the same
seam the real page uses (`client=api_state.get_client()`) without a live
server or a browser.

Known seeded alert (see db/seed.py): the SSH brute-force alert (external_id
ALERT-0001, database id 1 in a fresh seeded session) is CLOSED / Medium
severity and has 7 linked events, making it a good fixed point for the
detail-view, timeline/evidence, and status-mutation assertions below.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.components import api_state

SCRIPT_PATH = str(Path(__file__).parent / "_apptest_scripts" / "investigations_script.py")

BRUTE_FORCE_ALERT_ID = 1


@pytest.fixture()
def list_app(monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client) -> AppTest:
    """Run the Investigations list view against the seeded in-memory API."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(SCRIPT_PATH)
    at.run(timeout=15)
    assert not at.exception
    return at


@pytest.fixture()
def detail_app(monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client) -> AppTest:
    """Run the Investigations detail view for the known brute-force alert."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(SCRIPT_PATH)
    at.session_state["selected_alert"] = BRUTE_FORCE_ALERT_ID
    at.run(timeout=15)
    assert not at.exception
    return at


def _table_markup(at: AppTest) -> str:
    for element in at.markdown:
        if "soc-table-wrap" in element.value:
            return element.value
    raise AssertionError("Alerts table markup not found in rendered page.")


def test_list_view_renders_all_seeded_alerts(list_app: AppTest) -> None:
    """The alerts table and columns render correctly for the full seeded set (13 alerts, page size 20)."""
    table_markup = _table_markup(list_app)

    assert table_markup.count("<tr>") == 14  # 1 header + 13 seeded alerts
    for column in ["ID", "Alert", "Severity", "Status", "Host", "User", "Created"]:
        assert f"<th>{column}</th>" in table_markup

    page_info = next(
        element.value for element in list_app.markdown if "alerts</div>" in element.value
    )
    assert "Page 1 of 1" in page_info
    assert "13 alerts" in page_info


def test_detail_view_shows_alert_title_severity_and_status(detail_app: AppTest) -> None:
    """The detail view for the known brute-force alert shows its title, severity, and status."""
    card_markup = next(
        element.value for element in detail_app.markdown if "soc-section-card" in element.value
    )

    assert "Multiple Failed SSH Authentication Attempts" in card_markup
    assert "severity-medium" in card_markup and ">Medium<" in card_markup
    assert "status-resolved" in card_markup and ">Resolved<" in card_markup


def test_timeline_and_evidence_tabs_show_linked_event_count(detail_app: AppTest) -> None:
    """The Timeline and Evidence tabs show the 7 events linked to the brute-force alert."""
    tabs = detail_app.tabs
    tab_labels = [tab.label for tab in tabs]
    assert tab_labels == ["Overview", "Timeline", "Evidence", "MITRE", "Notes"]

    timeline_markup = tabs[tab_labels.index("Timeline")].markdown[0].value
    assert timeline_markup.count("soc-timeline-item") == 7

    evidence_markup = tabs[tab_labels.index("Evidence")].markdown[0].value
    assert evidence_markup.count("<tr>") == 8  # 1 header + 7 event rows


def test_update_status_mutates_and_rerenders_new_status(detail_app: AppTest) -> None:
    """Clicking Update Status persists the new status and the rerendered page reflects it."""
    status_select = detail_app.selectbox(key=f"status_select_{BRUTE_FORCE_ALERT_ID}")
    assert status_select.value == "Resolved"

    status_select.set_value("Investigating")
    detail_app.button(key=f"update_status_{BRUTE_FORCE_ALERT_ID}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    card_markup = next(
        element.value for element in detail_app.markdown if "soc-section-card" in element.value
    )
    assert "status-investigating" in card_markup and ">Investigating<" in card_markup

    # Status widget itself resets to the new value on rerender, proving the
    # detail view re-fetched the alert rather than just leaving stale state.
    refreshed_select = detail_app.selectbox(key=f"status_select_{BRUTE_FORCE_ALERT_ID}")
    assert refreshed_select.value == "Investigating"


def test_ai_assistance_requires_explicit_action_and_shows_unavailable_state(detail_app: AppTest) -> None:
    """AI does not run on detail load and handles the disabled provider safely."""
    assert detail_app.button(key=f"analyze_with_ai_{BRUTE_FORCE_ALERT_ID}")
    assert any("No AI analysis requested yet" in element.value for element in detail_app.info)

    detail_app.button(key=f"analyze_with_ai_{BRUTE_FORCE_ALERT_ID}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    assert any("unavailable" in element.value.lower() for element in detail_app.warning)
