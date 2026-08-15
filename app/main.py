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

from app.components.copilot import render_copilot_panel
from app.components.theme import apply_theme, render_sidebar_brand, render_sidebar_status
from app.views import (
    analyze_alert,
    dashboard,
    integrations,
    investigations,
    mitre_explorer,
    reports,
    settings,
    threat_intel,
)
from backend.services.health_service import HealthService
from backend.services.upload_service import AlertUploadService
from backend.utils.logging import get_logger, initialize_logging
from config.settings import AppConfig, load_config


RenderFunction = Callable[[AppConfig], None]


@dataclass(frozen=True)
class NavigationItem:
    """Purpose: Represent a selectable page in the Streamlit sidebar."""

    key: str
    label: str
    icon: str
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
            key="dashboard",
            label="Dashboard",
            icon="⌂",
            renderer=lambda config: dashboard.render(
                config=config,
                health_service=HealthService(config=config),
            ),
        ),
        "Analyze Alert": NavigationItem(
            key="analyze_alert",
            label="Analyze Alert",
            icon="◔",
            renderer=lambda config: analyze_alert.render(
                config=config,
                upload_service=AlertUploadService(config=config),
            ),
        ),
        "Investigations": NavigationItem(
            key="investigations",
            label="Investigations",
            icon="▤",
            renderer=investigations.render,
        ),
        "MITRE ATT&CK": NavigationItem(
            key="mitre_explorer",
            label="MITRE ATT&CK",
            icon="◈",
            renderer=mitre_explorer.render,
        ),
        "Threat Intelligence": NavigationItem(
            key="threat_intel",
            label="Threat Intelligence",
            icon="◎",
            renderer=threat_intel.render,
        ),
        "Reports": NavigationItem(
            key="reports",
            label="Reports",
            icon="▣",
            renderer=reports.render,
        ),
        "Integrations": NavigationItem(
            key="integrations",
            label="Integrations",
            icon="⛓",
            renderer=integrations.render,
        ),
        "Settings": NavigationItem(
            key="settings",
            label="Settings",
            icon="⚙",
            renderer=settings.render,
        ),
    }


def render_sidebar_navigation(navigation: dict[str, NavigationItem]) -> str:
    """Render the custom sidebar navigation and return the current selection.

    Args:
        navigation: Mapping of page names to nav metadata.

    Returns:
        Selected page name.
    """
    current_page = st.session_state.get("selected_page", "Dashboard")
    workflow_pages = [
        "Dashboard",
        "Analyze Alert",
        "Investigations",
        "MITRE ATT&CK",
        "Threat Intelligence",
        "Reports",
    ]
    system_pages = ["Integrations", "Settings"]

    def render_button(page_name: str) -> None:
        nonlocal current_page
        item = navigation[page_name]
        if st.sidebar.button(
            f"{item.icon} {item.label}",
            key=f"nav_{item.key}",
            use_container_width=True,
            type="primary" if current_page == page_name else "secondary",
        ):
            current_page = page_name

    for page_name in workflow_pages:
        render_button(page_name)

    st.sidebar.markdown('<div class="soc-sidebar-divider"></div>', unsafe_allow_html=True)
    for page_name in system_pages:
        render_button(page_name)

    st.session_state["selected_page"] = current_page
    return current_page


def main() -> None:
    """Load application dependencies and render the selected page."""
    config = load_config()
    initialize_logging(config=config)
    logger = get_logger(__name__)

    configure_streamlit_page(config)
    apply_theme()

    render_sidebar_brand(
        title=config.app_name,
        subtitle="Security Operations Assistant",
    )

    navigation = build_navigation()
    selection = render_sidebar_navigation(navigation)
    render_sidebar_status()

    logger.info("Rendering page", extra={"page": selection})
    navigation[selection].renderer(config)

    render_copilot_panel()


if __name__ == "__main__":
    main()
