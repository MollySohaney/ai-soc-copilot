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

from api_client.http import ApiClientError, build_client
from config.settings import load_config

__all__ = ["ApiClientError", "get_client", "loading", "render_empty_state", "render_error"]


@st.cache_resource
def get_client() -> httpx.Client:
    """Return the Streamlit-cached httpx client for the SOC API.

    Cached with `st.cache_resource` so every page in a session reuses one
    connection pool instead of opening a new client per rerun.

    Returns:
        A configured httpx client for the SOC API.
    """
    settings = load_config()
    base_url = f"{settings.api_base_url}/api/{settings.api_version}"
    return build_client(base_url)


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


def render_empty_state(message: str, *, icon: str = "info") -> None:
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
    if error.status_code == 404:
        st.error("The requested item could not be found.", icon="🚫")
    elif error.status_code is not None:
        st.error(f"The SOC API returned an error: {error.detail or error.message}", icon="⚠️")
    else:
        st.error(
            "Could not reach the SOC API. Confirm the API service is running and reachable.",
            icon="🔌",
        )
