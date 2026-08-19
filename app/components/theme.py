"""Purpose: Provide shared theming helpers for the Streamlit frontend."""

from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st

from .layout import dedent_html


THEME_PATH = Path(__file__).resolve().parents[1] / "styles" / "theme.css"


@lru_cache(maxsize=1)
def load_theme_stylesheet() -> str:
    """Load the shared application stylesheet.

    Returns:
        Raw CSS contents.
    """
    return THEME_PATH.read_text(encoding="utf-8")


def apply_theme() -> None:
    """Inject the shared CSS theme into the current Streamlit page."""
    st.markdown(f"<style>{load_theme_stylesheet()}</style>", unsafe_allow_html=True)


def render_sidebar_brand(title: str, subtitle: str = "") -> None:
    """Render custom branding at the top of the sidebar.

    Args:
        title: Product name.
        subtitle: Short supporting subtitle shown beneath the wordmark.
    """
    subtitle_markup = (
        f'<div style="color:#7282a9; font-size:0.74rem; letter-spacing:0.03em; margin-top:0.2rem;">{escape(subtitle)}</div>'
        if subtitle
        else ""
    )
    st.sidebar.markdown(
        dedent_html(f"""
        <div style="padding: 1.15rem 0 2.6rem; margin-top: 0.45rem;">
          <div style="display:flex; align-items:center; gap:0.9rem; min-height:54px;">
            <div style="
              width:52px; height:46px; border-radius:16px;
              background: radial-gradient(circle at top left, #89a5ff, #3556d8 58%, #15254d 100%);
              box-shadow: 0 10px 25px rgba(91, 124, 255, 0.35);
              display:flex; align-items:center; justify-content:center;
              color:white; font-size:1.1rem; font-weight:700;
              flex:0 0 auto;
            ">AI</div>
            <div>
              <div style="color:#f4f7ff; font-size:1.24rem; font-weight:800; letter-spacing:-0.03em; line-height:1; white-space:nowrap;">
                {escape(title)}
              </div>
              {subtitle_markup}
            </div>
          </div>
        </div>
        """),
        unsafe_allow_html=True,
    )


def render_sidebar_status() -> None:
    """Render the system status block pinned to the bottom of the sidebar."""
    st.sidebar.markdown(
        dedent_html("""
        <div class="soc-status-panel">
          <div class="soc-status-title">System Status</div>
          <div class="soc-status-row">
            <span>Local AI</span>
            <span class="soc-status-dot">Ready</span>
          </div>
          <div class="soc-status-row">
            <span>Threat Intel</span>
            <span class="soc-status-dot mock">Mock Mode</span>
          </div>
          <div class="soc-status-version">Version v0.1.0</div>
        </div>
        """),
        unsafe_allow_html=True,
    )


def render_shell_start(
    title: str,
    description: str,
    breadcrumb: str,
    status_chips: list[tuple[str, str]],
) -> None:
    """Render the opening markup for the primary glass shell.

    Args:
        title: Main page title.
        description: Supporting page description.
        breadcrumb: Context label shown above the title.
        status_chips: Key/value chips shown at the top right.
    """
    chip_markup = "".join(
        f'<div class="soc-chip"><strong>{escape(label)}:</strong> {escape(value)}</div>'
        for label, value in status_chips
    )
    st.markdown(
        dedent_html(f"""
        <section class="soc-shell">
          <div class="soc-topbar">
            <div>
              <div class="soc-breadcrumb">{escape(breadcrumb)}</div>
              <h1 class="soc-page-title">{title}</h1>
              <p class="soc-page-description">{escape(description)}</p>
            </div>
            <div class="soc-chip-row">{chip_markup}</div>
          </div>
        """),
        unsafe_allow_html=True,
    )


def render_shell_end() -> None:
    """Close the shared glass shell wrapper."""
    st.markdown("</section>", unsafe_allow_html=True)
