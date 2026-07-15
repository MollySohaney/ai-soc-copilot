"""Purpose: Provide shared theming helpers for the Streamlit frontend."""

from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st


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


def render_sidebar_brand(title: str, subtitle: str) -> None:
    """Render custom branding at the top of the sidebar.

    Args:
        title: Product name.
        subtitle: Short supporting description.
    """
    st.sidebar.markdown(
        f"""
        <div style="padding: 0.35rem 0 1.4rem;">
          <div style="display:flex; align-items:center; gap:0.8rem; margin-bottom:0.8rem;">
            <div style="
              width:44px; height:44px; border-radius:14px;
              background: radial-gradient(circle at top left, #89a5ff, #3556d8 58%, #15254d 100%);
              box-shadow: 0 10px 25px rgba(91, 124, 255, 0.35);
              display:flex; align-items:center; justify-content:center;
              color:white; font-size:1.15rem; font-weight:700;
            ">AI</div>
            <div>
              <div style="color:#f4f7ff; font-size:1.28rem; font-weight:800; letter-spacing:-0.03em;">
                {escape(title)}
              </div>
              <div style="color:#91a0c7; font-size:0.86rem; margin-top:0.12rem;">
                {escape(subtitle)}
              </div>
            </div>
          </div>
        </div>
        """,
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
        f"""
        <section class="soc-shell">
          <div class="soc-topbar">
            <div>
              <div class="soc-breadcrumb">{escape(breadcrumb)}</div>
              <h1 class="soc-page-title">{title}</h1>
              <p class="soc-page-description">{escape(description)}</p>
            </div>
            <div class="soc-chip-row">{chip_markup}</div>
          </div>
        """,
        unsafe_allow_html=True,
    )


def render_shell_end() -> None:
    """Close the shared glass shell wrapper."""
    st.markdown("</section>", unsafe_allow_html=True)
