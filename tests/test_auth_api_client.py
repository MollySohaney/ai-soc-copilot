"""Purpose: Verify typed authentication client contracts."""

from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from api_client import auth as auth_api
from backend.security.auth import create_user


def test_typed_auth_client_login_me_and_logout(
    api_client_transport: httpx.Client, db_session: Session
) -> None:
    """The typed client handles the complete opaque-session lifecycle."""
    password = "typed-client-test-password"
    user, _ = create_user(db_session, username="typed-client", password=password)
    db_session.commit()

    login = auth_api.login(user.username, password, client=api_client_transport)
    api_client_transport.headers["Authorization"] = f"Bearer {login.access_token}"

    current = auth_api.get_current_user(client=api_client_transport)
    assert current.username == user.username
    auth_api.logout(client=api_client_transport)
