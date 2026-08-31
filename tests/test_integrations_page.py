"""Purpose: Verify the Integrations page renders real ingestion data via AppTest."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from api_client.ingestion import sync_provider
from app.components import api_state
from db.seed import BASE_TIME

SCRIPT_PATH = str(Path(__file__).parent / "_apptest_scripts" / "integrations_script.py")


@pytest.fixture()
def integrations_app(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> AppTest:
    """Run the integrations page against the seeded in-memory API."""
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    sync_provider(
        "fixture",
        source_name="fixture-ui",
        start_time=BASE_TIME,
        end_time=BASE_TIME.replace(hour=4),
        limit=3,
        client=api_client_transport,
    )
    at = AppTest.from_file(SCRIPT_PATH)
    at.run(timeout=15)
    assert not at.exception
    return at


def test_integrations_page_renders_ingestion_controls(integrations_app: AppTest) -> None:
    """The page includes real ingestion provider controls."""
    labels = [control.label for control in integrations_app.segmented_control]
    button_labels = [button.label for button in integrations_app.button]

    assert "Provider" in labels
    assert "Test connection" in button_labels
    assert "Run bounded sync" in button_labels


def test_integrations_page_renders_ingestion_status(integrations_app: AppTest) -> None:
    """The page displays current ingestion run status from the API."""
    markdown = "\n".join(element.value for element in integrations_app.markdown)

    assert "Ingestion status" in markdown
    assert "Latest status" in markdown
    assert "succeeded" in markdown
    assert "Checkpoints" in markdown


def test_integrations_page_renders_recent_ingested_events(integrations_app: AppTest) -> None:
    """The page displays recently ingested events and raw evidence controls."""
    markdown = "\n".join(element.value for element in integrations_app.markdown)
    select_labels = [select.label for select in integrations_app.selectbox]
    expander_labels = [expander.label for expander in integrations_app.expander]

    assert "Recently ingested events" in markdown
    assert "Raw evidence event" in select_labels
    assert "Raw source evidence" in expander_labels
