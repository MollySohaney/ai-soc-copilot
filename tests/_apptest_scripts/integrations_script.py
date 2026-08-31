"""AppTest harness script: renders the Integrations page in isolation."""

from __future__ import annotations

import streamlit as st

from app.views import integrations
from config.settings import AppConfig

st.cache_data.clear()
st.cache_resource.clear()

config = AppConfig()
integrations.render(config=config)
