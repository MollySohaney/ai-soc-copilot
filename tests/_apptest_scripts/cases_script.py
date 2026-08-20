"""AppTest harness script: renders the Cases page in isolation.

Not app code — test-only entry point that `AppTest.from_file` executes as a
standalone Streamlit script. `app.components.api_state.get_client` is expected
to be monkeypatched by the calling test *before* `AppTest.run()` so every
`api_client` call in the page hits the seeded in-memory API instead of a real
network client.
"""

from __future__ import annotations

import streamlit as st

from app.views import cases
from config.settings import AppConfig

st.cache_data.clear()
st.cache_resource.clear()

config = AppConfig()
cases.render(config=config)
