"""Purpose: Verify Streamlit hides role-inappropriate actions."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from app.components import api_state

SCRIPTS = Path(__file__).parent / "_apptest_scripts"


def _run_page(
    monkeypatch: pytest.MonkeyPatch,
    api_client_transport: httpx.Client,
    script_name: str,
    *,
    role: str,
    selected_key: str | None = None,
    selected_id: int | None = None,
) -> AppTest:
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    app = AppTest.from_file(str(SCRIPTS / script_name))
    app.session_state["_test_role"] = role
    if selected_key is not None:
        app.session_state[selected_key] = selected_id
    app.run(timeout=15)
    assert not app.exception
    return app


def _button_keys(app: AppTest) -> set[str]:
    return {button.key for button in app.button if button.key is not None}


def test_viewer_can_read_rules_but_has_no_rule_mutation_controls(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Read-only detection pages do not offer create, edit, toggle, test, or run."""
    app = _run_page(
        monkeypatch, api_client_transport, "rules_script.py", role="viewer"
    )
    keys = _button_keys(app)

    assert any("SSH Brute Force Detection" in item.value for item in app.markdown)
    assert not any("create_rule" in key for key in keys)
    assert not any(key.startswith("toggle_rule_") for key in keys)
    assert not any(key.startswith("test_rule_") for key in keys)
    assert not any(key.startswith("run_rule_") for key in keys)


def test_detection_engineer_sees_detection_controls(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Detection Engineers receive rule controls without relying on Admin role."""
    app = _run_page(
        monkeypatch,
        api_client_transport,
        "rules_script.py",
        role="detection_engineer",
    )
    keys = _button_keys(app)

    assert any("create_rule" in key for key in keys)
    assert any(key.startswith("toggle_rule_") for key in keys)
    assert any(key.startswith("test_rule_") for key in keys)


def test_viewer_investigation_is_read_only_and_cannot_request_ai(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Viewer alert details retain evidence while removing mutation/AI actions."""
    app = _run_page(
        monkeypatch,
        api_client_transport,
        "investigations_script.py",
        role="viewer",
        selected_key="selected_alert",
        selected_id=1,
    )
    keys = _button_keys(app)

    assert "update_status_1" not in keys
    assert "escalate_to_case_1" not in keys
    assert "analyze_with_ai_1" not in keys
    assert any("Multiple Failed SSH" in item.value for item in app.markdown)


def test_analyst_sees_investigation_and_ai_actions(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Analysts receive the investigation and advisory AI affordances they can invoke."""
    app = _run_page(
        monkeypatch,
        api_client_transport,
        "investigations_script.py",
        role="analyst",
        selected_key="selected_alert",
        selected_id=1,
    )
    keys = _button_keys(app)

    assert {"update_status_1", "escalate_to_case_1", "analyze_with_ai_1"} <= keys


def test_viewer_case_detail_hides_mutation_controls(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Viewer case details expose history but no link, note, or update controls."""
    app = _run_page(
        monkeypatch,
        api_client_transport,
        "cases_script.py",
        role="viewer",
        selected_key="selected_case",
        selected_id=1,
    )
    keys = _button_keys(app)

    assert "update_case_1" not in keys
    assert "add_alert_button_1" not in keys
    assert "add_case_note_1" not in keys
    assert not any(key.startswith("remove_alert_1_") for key in keys)
    assert any("SSH Brute Force to Persistence" in item.value for item in app.markdown)


def test_non_admin_cannot_render_integration_controls(
    monkeypatch: pytest.MonkeyPatch, api_client_transport: httpx.Client
) -> None:
    """Direct page rendering still guards Admin-only integration operations."""
    app = _run_page(
        monkeypatch,
        api_client_transport,
        "integrations_script.py",
        role="analyst",
    )

    assert any("cannot operate integrations" in item.value for item in app.error)
    assert not app.segmented_control
