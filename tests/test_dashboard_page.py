"""Purpose: Verify the Dashboard page renders real seeded data via AppTest.

Script-runs `app/views/dashboard.py`'s `render()` through Streamlit's
`AppTest`, with `api_state.get_client` monkeypatched to the seeded
in-memory API (`api_client_transport`), so assertions exercise the same
seam the real page uses (`client=api_state.get_client()`) without a live
server or a browser.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.components import api_state

SCRIPT_PATH = str(Path(__file__).parent / "_apptest_scripts" / "dashboard_script.py")


@pytest.fixture()
def dashboard_app(monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client) -> AppTest:
    """Run the dashboard page against the seeded in-memory API."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    at = AppTest.from_file(SCRIPT_PATH)
    at.run(timeout=15)
    assert not at.exception
    return at


def _metric_grid_markup(at: AppTest) -> str:
    for element in at.markdown:
        if "soc-kpi-grid" in element.value:
            return element.value
    raise AssertionError("Metric grid markup not found in rendered dashboard.")


def _severity_rows_markup(at: AppTest) -> list[str]:
    return [element.value for element in at.markdown if "soc-status-row" in element.value]


def _recent_alerts_table_markup(at: AppTest) -> str:
    for element in at.markdown:
        if "soc-table-wrap" in element.value:
            return element.value
    raise AssertionError("Recent alerts table markup not found in rendered dashboard.")


def test_metric_cards_match_seeded_totals(dashboard_app: AppTest) -> None:
    """The four KPI cards reflect the known seeded alert/case totals."""
    markup = _metric_grid_markup(dashboard_app)

    assert "Total Alerts" in markup and "13" in markup
    assert "Critical Alerts" in markup and "2" in markup
    assert "In Progress Alerts" in markup and "4" in markup
    assert "Open Cases" in markup and "2" in markup


def test_severity_distribution_values_appear(dashboard_app: AppTest) -> None:
    """The severity breakdown list shows the known seeded counts for every severity."""
    rows = _severity_rows_markup(dashboard_app)
    combined = "\n".join(rows)
    assert "Low" in combined and "4" in combined
    assert "Medium" in combined and "4" in combined
    assert "High" in combined and "3" in combined
    assert "Critical" in combined and "2" in combined
    assert combined.count("soc-status-row") == 4


def test_recent_alerts_table_renders_expected_row_count(dashboard_app: AppTest) -> None:
    """The recent alerts table renders exactly the requested limit of rows (6)."""
    table_markup = _recent_alerts_table_markup(dashboard_app)

    # 1 header <tr> + 6 data rows, matching dashboard.py's `_load_recent_alerts(limit=6)`.
    assert table_markup.count("<tr>") == 7
    assert "Scheduled Maintenance Login Burst on db-prod-01" in table_markup
