"""Purpose: Verify the Streamlit login boundary and safe session state."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy.orm import Session
from streamlit.testing.v1 import AppTest

from app.components import api_state
from backend.security.auth import create_user

SCRIPT_PATH = Path(__file__).parent / "_apptest_scripts" / "auth_script.py"


@pytest.fixture()
def login_app(
    monkeypatch: pytest.MonkeyPatch,
    api_client_transport: httpx.Client,
    db_session: Session,
) -> tuple[AppTest, str, str]:
    """Render login against the in-memory authenticated API transport."""
    username = "streamlit-user"
    password = "streamlit-test-password"
    create_user(db_session, username=username, password=password)
    db_session.commit()
    monkeypatch.setattr(api_state, "get_public_client", lambda: api_client_transport)
    monkeypatch.setattr(api_state, "get_client", lambda: api_client_transport)
    return AppTest.from_file(SCRIPT_PATH).run(), username, password


def test_login_form_masks_password_and_reports_generic_failure(
    login_app: tuple[AppTest, str, str],
) -> None:
    """The credential form batches input and never renders the entered password."""
    app, username, _ = login_app
    app.text_input(key="login_username").input(username)
    app.text_input(key="login_password").input("wrong-test-password")
    app.button[0].click().run()

    assert any("Invalid username or password" in item.value for item in app.error)
    rendered_messages = " ".join(
        item.value for collection in (app.error, app.warning, app.success) for item in collection
    )
    assert "wrong-test-password" not in rendered_messages


def test_successful_login_enters_authenticated_state(
    login_app: tuple[AppTest, str, str],
) -> None:
    """A valid login reruns into authenticated content without rendering a token."""
    app, username, password = login_app
    app.text_input(key="login_username").input(username)
    app.text_input(key="login_password").input(password)
    app.button[0].click().run()

    assert any("Signed in as" in item.value for item in app.success)
    assert password not in str(app)
