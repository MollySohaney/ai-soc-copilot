"""Purpose: Provide dashboard summary data for the application shell."""

from __future__ import annotations

from backend.models.dashboard import DashboardMetric
from config.settings import AppConfig


class HealthService:
    """Provide lightweight dashboard metrics for the current scaffold."""

    def __init__(self, config: AppConfig) -> None:
        """Store configuration needed for dashboard rendering.

        Args:
            config: Loaded application configuration.
        """
        self._config = config

    def get_dashboard_metrics(self) -> list[DashboardMetric]:
        """Return static platform metrics for the scaffold.

        Returns:
            List of dashboard metrics.
        """
        return [
            DashboardMetric(label="Environment", value=self._config.environment.upper()),
            DashboardMetric(label="Upload Types", value=str(len(self._config.allowed_upload_types))),
            DashboardMetric(label="Max Upload Size", value=f"{self._config.max_upload_size_mb} MB"),
        ]
