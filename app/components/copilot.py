"""Purpose: Render the global floating SOC Copilot assistant panel."""

from __future__ import annotations

from html import escape

import streamlit as st

from ..data.mock_data import COPILOT_CONVERSATION
from .layout import render_html_block

MOCK_REPLY = (
    "This is a mock response. Once connected to a local or hosted AI provider, SOC Copilot will "
    "answer questions about the current alert, investigation, or indicator using live context."
)


def _render_conversation() -> None:
    history = st.session_state.setdefault("copilot_history", list(COPILOT_CONVERSATION))
    for message in history:
        role_label = "Analyst" if message["role"] == "analyst" else "SOC Copilot"
        render_html_block(
            f"""
            <div class="soc-copilot-message {message['role']}">
              <div class="soc-copilot-role">{role_label}</div>
              {escape(message['text'])}
            </div>
            """
        )


def render_copilot_panel() -> None:
    """Render the floating Ask Copilot trigger and, when open, the assistant panel.

    The sidebar remains untouched — the panel is positioned fixed on the right edge
    of the viewport via the ``st-key-*`` CSS hooks defined in theme.css.
    """
    st.session_state.setdefault("copilot_open", False)

    with st.container(key="copilot_trigger"):
        label = "Close Copilot" if st.session_state["copilot_open"] else "💬 Ask Copilot"
        if st.button(label, key="copilot_toggle_button"):
            st.session_state["copilot_open"] = not st.session_state["copilot_open"]
            st.rerun()

    if not st.session_state["copilot_open"]:
        return

    with st.container(key="copilot_panel"):
        render_html_block(
            """
            <div class="soc-card-label">SOC ASSISTANT</div>
            <h3 class="soc-card-title" style="font-size:1.15rem;">SOC Copilot</h3>
            <p class="soc-card-subtitle">Ask about the current alert or investigation.</p>
            <div style="height:1px; background:rgba(133,164,255,0.14); margin:0.9rem 0;"></div>
            """
        )
        _render_conversation()

        st.text_input(
            "Ask about this investigation...",
            key="copilot_input",
            placeholder="Ask about this investigation...",
            label_visibility="collapsed",
        )
        col_send, col_clear = st.columns(2)
        with col_send:
            if st.button("Send", type="primary", use_container_width=True, key="copilot_send"):
                question = st.session_state.get("copilot_input", "").strip()
                if question:
                    history = st.session_state.setdefault("copilot_history", list(COPILOT_CONVERSATION))
                    history.append({"role": "analyst", "text": question})
                    history.append({"role": "copilot", "text": MOCK_REPLY})
                    st.rerun()
        with col_clear:
            if st.button("Clear", use_container_width=True, key="copilot_clear"):
                st.session_state["copilot_history"] = list(COPILOT_CONVERSATION)
                st.rerun()
