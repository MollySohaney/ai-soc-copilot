"""Purpose: Render the local authentication experience for Streamlit."""

from __future__ import annotations

import streamlit as st

from api_client import auth as auth_api
from api_client.http import ApiClientError
from app.components import api_state
from config.settings import AppConfig


def render_login(config: AppConfig, *, message: str | None = None) -> None:
    """Render a batched credential form without retaining the password."""
    st.title(config.app_name)
    st.caption("Sign in to access the SOC workspace.")
    if message:
        st.warning(message, icon=":material/info:")

    with st.container(border=True):
        with st.form("local_login", clear_on_submit=True):
            username = st.text_input(
                "Username",
                autocomplete="username",
                key="login_username",
            )
            password = st.text_input(
                "Password",
                type="password",
                autocomplete="current-password",
                key="login_password",
            )
            submitted = st.form_submit_button(
                "Sign in",
                type="primary",
                icon=":material/login:",
                width="stretch",
            )

    if not submitted:
        return
    try:
        response = auth_api.login(username, password, client=api_state.get_public_client())
    except ApiClientError as error:
        if error.status_code == 429:
            st.error("Too many login attempts. Try again later.", icon=":material/timer:")
        elif error.status_code == 401:
            st.error("Invalid username or password.", icon=":material/lock:")
        else:
            st.error("Could not reach the SOC API.", icon=":material/cloud_off:")
        return

    api_state.establish_authenticated_session(response)
    st.rerun()
