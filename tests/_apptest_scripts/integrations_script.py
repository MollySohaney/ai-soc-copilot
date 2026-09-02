"""AppTest harness script: renders the Integrations page in isolation."""

from __future__ import annotations

import streamlit as st

from app.views import integrations
from config.settings import AppConfig

test_role = st.session_state.get("_test_role", "admin")
st.session_state["_auth_user"] = {
    "id": 1,
    "username": "test-admin",
    "role": test_role,
    "is_active": True,
}

st.cache_data.clear()
st.cache_resource.clear()

config = AppConfig()
integrations.render(config=config)
