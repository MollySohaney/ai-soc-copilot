"""Purpose: Bridge the framework-agnostic api_client layer into Streamlit page state.

This is the only module in the frontend allowed to import both `streamlit` and
`api_client` — it keeps `api_client/` itself standalone and unit-testable without
a Streamlit runtime.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import httpx
import streamlit as st

from api.schemas.auth import LoginResponse, UserRead
from api_client import auth as auth_api
from api_client.http import ApiClientError, build_client
from config.settings import load_config

__all__ = [
    "ApiClientError",
    "clear_authenticated_session",
    "establish_authenticated_session",
    "get_client",
    "get_current_user",
    "get_public_client",
    "loading",
    "logout",
    "render_empty_state",
    "render_error",
    "validate_authenticated_session",
]

_TOKEN_KEY = "_auth_access_token"
_USER_KEY = "_auth_user"
_CLIENT_KEY = "_auth_api_client"
_MESSAGE_KEY = "_auth_message"


def _base_url() -> str:
    settings = load_config()
    return f"{settings.api_base_url}/api/{settings.api_version}"


@st.cache_resource
def get_public_client() -> httpx.Client:
    """Return a credential-free shared client used only for login."""
    return build_client(_base_url())


def get_client() -> httpx.Client:
    """Return the current browser session's authenticated API client.

    Authenticated clients cannot use ``st.cache_resource`` because that cache is
    process-wide and could share one user's bearer token with another session.

    Returns:
        A configured httpx client for the SOC API.
    """
    token = st.session_state.get(_TOKEN_KEY)
    if not isinstance(token, str) or not token:
        raise ApiClientError("Authentication required.", status_code=401)
    client = st.session_state.get(_CLIENT_KEY)
    if not isinstance(client, httpx.Client):
        client = build_client(_base_url(), headers={"Authorization": f"Bearer {token}"})
        st.session_state[_CLIENT_KEY] = client
    return client


def establish_authenticated_session(response: LoginResponse) -> None:
    """Store a bearer token only in this tab's server-side Streamlit state."""
    clear_authenticated_session()
    st.session_state[_TOKEN_KEY] = response.access_token
    st.session_state[_USER_KEY] = response.user.model_dump()


def clear_authenticated_session() -> None:
    """Close the authenticated client and remove all per-user page state."""
    client = st.session_state.get(_CLIENT_KEY)
    if isinstance(client, httpx.Client):
        client.close()
    st.session_state.clear()


def get_current_user() -> UserRead | None:
    """Return the safe cached identity for this Streamlit session."""
    value = st.session_state.get(_USER_KEY)
    if isinstance(value, dict):
        return UserRead.model_validate(value)
    return None


def validate_authenticated_session() -> tuple[bool, str | None]:
    """Refresh the identity or return a safe login-page message."""
    if not st.session_state.get(_TOKEN_KEY):
        return False, st.session_state.pop(_MESSAGE_KEY, None)
    try:
        user = auth_api.get_current_user(client=get_client())
    except ApiClientError as error:
        if error.status_code == 401:
            clear_authenticated_session()
            return False, "Your session expired or was revoked. Sign in again."
        return False, "The SOC API is unavailable, so your session could not be verified."
    st.session_state[_USER_KEY] = user.model_dump()
    return True, None


def logout() -> None:
    """Best-effort revoke the API session and always clear local state."""
    try:
        auth_api.logout(client=get_client())
    except ApiClientError:
        pass
    finally:
        clear_authenticated_session()


@contextmanager
def loading(message: str = "Loading...") -> Iterator[None]:
    """Show a spinner around a block of API calls.

    Args:
        message: The message displayed alongside the spinner.

    Yields:
        Control to the wrapped block.
    """
    with st.spinner(message):
        yield


def render_empty_state(message: str, *, icon: str = "ℹ️") -> None:
    """Render a placeholder for a successful call that returned no data.

    Args:
        message: The message explaining why there is nothing to show.
        icon: The Streamlit status icon to display alongside the message.
    """
    st.info(message, icon=icon)


def render_error(error: ApiClientError) -> None:
    """Render a user-readable error banner for a failed SOC API call.

    Args:
        error: The error raised by the api_client layer.
    """
    if error.status_code == 401:
        clear_authenticated_session()
        st.session_state[_MESSAGE_KEY] = "Your session expired or was revoked. Sign in again."
        st.rerun()
    elif error.status_code == 404:
        st.error("The requested item could not be found.", icon="🚫")
    elif error.status_code is not None:
        st.error(f"The SOC API returned an error: {error.detail or error.message}", icon="⚠️")
    else:
        st.error(
            "Could not reach the SOC API. Confirm the API service is running and reachable.",
            icon="🔌",
        )
