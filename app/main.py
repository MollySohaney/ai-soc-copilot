"""Purpose: Provide the Streamlit entry point for AI SOC Copilot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

import streamlit as st

# Ensure the project root is importable when Streamlit executes this file directly.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.components.theme import apply_theme, render_sidebar_brand
from app.views import analyze_alert, dashboard, mitre_explorer, reports, settings
from backend.services.health_service import HealthService
from backend.services.upload_service import AlertUploadService
from backend.utils.logging import get_logger, initialize_logging
from config.settings import AppConfig, load_config


RenderFunction = Callable[[AppConfig], None]


@dataclass(frozen=True)
class NavigationItem:
    """Purpose: Represent a selectable page in the Streamlit sidebar."""

    label: str
    renderer: RenderFunction


def configure_streamlit_page(config: AppConfig) -> None:
    """Set page-level Streamlit metadata.

    Args:
        config: Application configuration loaded during startup.
    """
    st.set_page_config(
        page_title=config.app_name,
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )


def build_navigation() -> dict[str, NavigationItem]:
    """Create the page registry for sidebar navigation.

    Returns:
        Mapping of page names to their corresponding renderers.
    """
    return {
        "Dashboard": NavigationItem(
            label="Dashboard",
            renderer=lambda config: dashboard.render(
                config=config,
                health_service=HealthService(config=config),
            ),
        ),
        "Analyze Alert": NavigationItem(
            label="Analyze Alert",
            renderer=lambda config: analyze_alert.render(
                config=config,
                upload_service=AlertUploadService(config=config),
            ),
        ),
        "MITRE Explorer": NavigationItem(
            label="MITRE Explorer",
            renderer=mitre_explorer.render,
        ),
        "Reports": NavigationItem(
            label="Reports",
            renderer=lambda config: reports.render(config=config),
        ),
        "Settings": NavigationItem(
            label="Settings",
            renderer=settings.render,
        ),
    }


def main() -> None:
    """Load application dependencies and render the selected page."""
    config = load_config()
    initialize_logging(config=config)
    logger = get_logger(__name__)

    configure_streamlit_page(config)
    apply_theme()

    render_sidebar_brand(
        title=config.app_name,
        subtitle="AI-assisted security operations workspace",
    )

    navigation = build_navigation()
    selection = st.sidebar.radio(
        label="Navigate",
        options=list(navigation.keys()),
        index=0,
    )

    logger.info("Rendering page", extra={"page": selection})
    navigation[selection].renderer(config)


if __name__ == "__main__":
    main()
