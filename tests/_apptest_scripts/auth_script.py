"""AppTest harness for the authenticated Streamlit entry boundary."""

from __future__ import annotations

import streamlit as st

from app.components import api_state
from app.components.auth import render_login
from config.settings import AppConfig


authenticated, message = api_state.validate_authenticated_session()
if authenticated:
    user = api_state.get_current_user()
    st.success(f"Signed in as {user.username if user else 'unknown'}")
else:
    render_login(AppConfig(), message=message)
