"""Purpose: Verify the Cases page against real seeded data via AppTest.

Script-runs `app/views/cases.py`'s `render()` (and, for the escalate-to-case
flow, `app/views/investigations.py`'s `render()`) through Streamlit's
`AppTest`, with `api_state.get_client` monkeypatched to the seeded in-memory
API (`api_client_transport`), so assertions exercise the same seam the real
pages use (`client=api_state.get_client()`) without a live server or a
browser.

Known seeded cases (see db/seed.py):
- CASE-2026-0001 (id 1): the SSH attack-chain case, IN_PROGRESS/CRITICAL,
  assignee analyst.rivera, 6 linked alerts (ids 1-6), 5 activity entries.
- CASE-2026-0002 (id 2): RESOLVED/MEDIUM, assignee analyst.chen, 2 linked
  alerts (ids 7, 8), 2 activity entries.
- CASE-2026-0003 (id 3): OPEN/LOW, unassigned, 1 linked alert (id 11), 1
  activity entry.

Filler alerts 9 (ALERT-1003) and 10 (ALERT-1004) are seeded but not linked to
any case, making them safe fixed points for add/remove-alert assertions.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from api_client import cases as cases_api
from app.components import api_state
from db.models.enums import CaseStatusEnum

CASES_SCRIPT_PATH = str(Path(__file__).parent / "_apptest_scripts" / "cases_script.py")
INVESTIGATIONS_SCRIPT_PATH = str(
    Path(__file__).parent / "_apptest_scripts" / "investigations_script.py"
)

CHAIN_CASE_ID = 1
REVIEW_CASE_ID = 2
LOGIN_CASE_ID = 3
UNLINKED_ALERT_ID = 9  # ALERT-1003, not linked to any seeded case
FILLER_ALERT_ID = 10  # ALERT-1004, not linked to any seeded case


@pytest.fixture()
def list_app(monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client) -> AppTest:
    """Run the Cases list view against the seeded in-memory API."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(CASES_SCRIPT_PATH)
    at.run(timeout=15)
    assert not at.exception
    return at


@pytest.fixture()
def detail_app(monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client) -> AppTest:
    """Run the Cases detail view for the known attack-chain case."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(CASES_SCRIPT_PATH)
    at.session_state["selected_case"] = CHAIN_CASE_ID
    at.run(timeout=15)
    assert not at.exception
    return at


def _table_markup(at: AppTest) -> str:
    for element in at.markdown:
        if "soc-table-wrap" in element.value:
            return element.value
    raise AssertionError("Cases table markup not found in rendered page.")


def _alerts_tab_markup(at: AppTest) -> str:
    tabs = at.tabs
    labels = [tab.label for tab in tabs]
    return "".join(element.value for element in tabs[labels.index("Alerts")].markdown)


def _activity_tab_markup(at: AppTest) -> str:
    tabs = at.tabs
    labels = [tab.label for tab in tabs]
    return "".join(element.value for element in tabs[labels.index("Activity")].markdown)


def test_list_view_renders_all_seeded_cases(list_app: AppTest) -> None:
    """The cases table renders the full seeded set (3 cases) with the expected columns."""
    table_markup = _table_markup(list_app)

    assert table_markup.count("<tr>") == 4  # 1 header + 3 seeded cases
    for column in ["Case #", "Title", "Priority", "Status", "Assignee", "Created"]:
        assert f"<th>{column}</th>" in table_markup
    assert "CASE-2026-0001" in table_markup
    assert "CASE-2026-0002" in table_markup
    assert "CASE-2026-0003" in table_markup


def test_list_view_filter_by_assignee_narrows_results(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Filtering by assignee "analyst.chen" narrows the table to just CASE-2026-0002."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(CASES_SCRIPT_PATH)
    at.run(timeout=15)
    assert not at.exception

    at.text_input(key="cases_filter_assignee").set_value("analyst.chen")
    at.run(timeout=15)
    assert not at.exception

    table_markup = _table_markup(at)
    assert table_markup.count("<tr>") == 2  # 1 header + 1 matching case
    assert "CASE-2026-0002" in table_markup
    assert "CASE-2026-0001" not in table_markup
    assert "CASE-2026-0003" not in table_markup


def test_detail_view_shows_case_title_priority_and_status(detail_app: AppTest) -> None:
    """The detail view for the known attack-chain case shows its title, priority, and status."""
    card_markup = next(
        element.value for element in detail_app.markdown if "soc-section-card" in element.value
    )

    assert "SSH Brute Force to Persistence" in card_markup
    assert "CASE-2026-0001" in card_markup
    assert "severity-critical" in card_markup and ">Critical<" in card_markup
    assert "status-investigating" in card_markup and ">Investigating<" in card_markup


def test_detail_view_shows_six_linked_alerts(detail_app: AppTest) -> None:
    """The Alerts tab shows the 6 alerts linked to the attack-chain case."""
    alerts_markup = _alerts_tab_markup(detail_app)
    assert alerts_markup.count("soc-alert-row") == 6


def test_detail_view_shows_five_activity_entries(detail_app: AppTest) -> None:
    """The Activity tab shows the 5 activity entries recorded for the attack-chain case."""
    activity_markup = _activity_tab_markup(detail_app)
    assert activity_markup.count("soc-timeline-item") == 5
    assert "Case opened after correlated attack-chain alert" in activity_markup


def test_add_alert_mutates_and_rerenders_new_alert_count(detail_app: AppTest) -> None:
    """Adding an unlinked alert persists the link and the rerendered Alerts tab reflects it."""
    tabs = detail_app.tabs
    labels = [tab.label for tab in tabs]
    alerts_tab = tabs[labels.index("Alerts")]

    alerts_tab.number_input(key=f"add_alert_id_{CHAIN_CASE_ID}").set_value(UNLINKED_ALERT_ID)
    alerts_tab.button(key=f"add_alert_button_{CHAIN_CASE_ID}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    alerts_markup = _alerts_tab_markup(detail_app)
    assert alerts_markup.count("soc-alert-row") == 7
    assert f"#{UNLINKED_ALERT_ID}" in alerts_markup


def test_remove_alert_mutates_and_rerenders_new_alert_count(detail_app: AppTest) -> None:
    """Removing a linked alert persists the unlink and the rerendered Alerts tab reflects it."""
    tabs = detail_app.tabs
    labels = [tab.label for tab in tabs]
    alerts_tab = tabs[labels.index("Alerts")]

    removed_alert_id = 6  # the "chain" alert, linked to CASE-2026-0001
    alerts_tab.button(key=f"remove_alert_{CHAIN_CASE_ID}_{removed_alert_id}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    alerts_markup = _alerts_tab_markup(detail_app)
    assert alerts_markup.count("soc-alert-row") == 5
    assert f"#{removed_alert_id}" not in alerts_markup


def test_add_note_appears_in_activity_tab_on_rerender(detail_app: AppTest) -> None:
    """Submitting a note via the Activity tab form persists it and it appears on rerender."""
    tabs = detail_app.tabs
    labels = [tab.label for tab in tabs]
    activity_tab = tabs[labels.index("Activity")]
    note_text = "Escalated to firewall team for blocking of 192.168.64.2."

    activity_tab.text_area(key=f"case_note_input_{CHAIN_CASE_ID}").set_value(note_text)
    activity_tab.button(key=f"add_case_note_{CHAIN_CASE_ID}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    activity_markup = _activity_tab_markup(detail_app)
    assert activity_markup.count("soc-timeline-item") == 6
    assert note_text in activity_markup


def test_update_status_and_priority_mutates_and_rerenders(detail_app: AppTest) -> None:
    """Updating status and priority persists the change and the rerendered card reflects it."""
    status_select = detail_app.selectbox(key=f"case_status_select_{CHAIN_CASE_ID}")
    assert status_select.value == "Investigating"
    status_select.set_value("Resolved")

    priority_select = detail_app.selectbox(key=f"case_priority_select_{CHAIN_CASE_ID}")
    assert priority_select.value == "critical"
    priority_select.set_value("low")

    detail_app.button(key=f"update_case_{CHAIN_CASE_ID}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    card_markup = next(
        element.value for element in detail_app.markdown if "soc-section-card" in element.value
    )
    assert "status-resolved" in card_markup and ">Resolved<" in card_markup
    assert "severity-low" in card_markup and ">Low<" in card_markup

    # Widgets themselves reset to the new values on rerender, proving the
    # detail view re-fetched the case rather than just leaving stale state.
    refreshed_status = detail_app.selectbox(key=f"case_status_select_{CHAIN_CASE_ID}")
    assert refreshed_status.value == "Resolved"
    refreshed_priority = detail_app.selectbox(key=f"case_priority_select_{CHAIN_CASE_ID}")
    assert refreshed_priority.value == "low"


def test_create_case_increases_count_and_is_retrievable(
    list_app: AppTest, api_client_transport: httpx.Client
) -> None:
    """Submitting the Create Case form increases the case count and the new case is retrievable."""
    before = cases_api.list_cases(page_size=50, client=api_client_transport)
    assert before.total == 3

    list_app.text_input(key="new_case_title").set_value("Suspicious PowerShell Activity")
    list_app.text_area(key="new_case_description").set_value("Investigating flagged PowerShell use.")
    list_app.selectbox(key="new_case_priority").set_value("high")
    list_app.text_input(key="new_case_assignee").set_value("analyst.rivera")
    list_app.button(key="FormSubmitter:create_case_form-Create Case").click()
    list_app.run(timeout=15)

    assert not list_app.exception

    after = cases_api.list_cases(page_size=50, client=api_client_transport)
    assert after.total == 4
    created = next(c for c in after.items if c.title == "Suspicious PowerShell Activity")
    assert created.priority.value == "high"
    assert created.assignee == "analyst.rivera"

    # Successful creation navigates straight into the new case's detail view.
    card_markup = next(
        element.value for element in list_app.markdown if "soc-section-card" in element.value
    )
    assert "Suspicious PowerShell Activity" in card_markup


def test_add_nonexistent_alert_renders_error_banner_not_crash(detail_app: AppTest) -> None:
    """Adding a nonexistent alert id surfaces an error banner instead of crashing the page."""
    tabs = detail_app.tabs
    labels = [tab.label for tab in tabs]
    alerts_tab = tabs[labels.index("Alerts")]

    alerts_tab.number_input(key=f"add_alert_id_{CHAIN_CASE_ID}").set_value(999999)
    alerts_tab.button(key=f"add_alert_button_{CHAIN_CASE_ID}").click()
    detail_app.run(timeout=15)

    assert not detail_app.exception
    assert len(detail_app.error) >= 1
    assert "could not be found" in detail_app.error[0].value.lower()

    # The alert count is unchanged since the mutation was rejected.
    alerts_markup = _alerts_tab_markup(detail_app)
    assert alerts_markup.count("soc-alert-row") == 6


def test_escalate_alert_to_case_creates_new_case_with_alert(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Escalating a known alert from Investigations creates a new case containing that alert."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(INVESTIGATIONS_SCRIPT_PATH)
    at.session_state["selected_alert"] = FILLER_ALERT_ID
    at.run(timeout=15)
    assert not at.exception

    at.button(key=f"escalate_to_case_{FILLER_ALERT_ID}").click()
    at.run(timeout=15)
    assert not at.exception

    all_cases = cases_api.list_cases(page_size=50, client=api_client_transport)
    assert all_cases.total == 4
    new_case = next(
        c for c in all_cases.items if c.title.startswith("Investigate:")
    )
    detail = cases_api.get_case(new_case.id, client=api_client_transport)
    assert any(alert.id == FILLER_ALERT_ID for alert in detail.alerts)
    assert detail.status == CaseStatusEnum.OPEN
