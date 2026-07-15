"""Purpose: Render the high-level dashboard experience."""

from __future__ import annotations

from ..components.layout import render_html_block, render_metric_cards, render_stat_list
from ..components.theme import render_shell_end, render_shell_start
from backend.services.health_service import HealthService
from config.settings import AppConfig


def render(config: AppConfig, health_service: HealthService) -> None:
    """Render the dashboard page.

    Args:
        config: Application configuration.
        health_service: Service that provides dashboard summary data.
    """
    render_shell_start(
        title="Dashboard",
        description=(
            "Operational overview for analyst triage, evidence intake, and platform readiness. "
            "The current release focuses on foundation work, not live detections."
        ),
        breadcrumb="SOC workspace / overview",
        status_chips=[
            ("Environment", config.environment.upper()),
            ("Upload types", str(len(config.allowed_upload_types))),
            ("Logging", config.log_level),
        ],
    )

    render_metric_cards(health_service.get_dashboard_metrics())

    render_html_block(
        """
        <div class="soc-grid">
          <div class="soc-stack">
            <div class="soc-card glow">
              <div class="soc-card-label">Priority workflow</div>
              <h3 class="soc-card-title">Foundation buildout for analyst-facing alert triage</h3>
              <p class="soc-card-subtitle">
                Core upload, validation, configuration, and reporting boundaries are in place so
                future AI services can be integrated behind controlled interfaces.
              </p>
            </div>
            <div class="soc-card">
              <div class="soc-card-label">Operational queue</div>
              <div class="soc-event">
                <div class="soc-event-top">
                  <span class="soc-badge severity-high">High severity</span>
                  <span class="soc-badge">EDR pipeline</span>
                </div>
                <h4 class="soc-event-title">Suspicious PowerShell execution upload path</h4>
                <p class="soc-event-copy">
                  Validate ingest behavior for encoded command telemetry and ensure analyst previews
                  remain readable before AI enrichment is introduced.
                </p>
                <div class="soc-inline-list">
                  <span>Owner: Platform engineering</span>
                  <span>State: In progress</span>
                  <span>Focus: Parser hardening</span>
                </div>
                <div class="soc-progress">
                  <div class="soc-progress-label">Foundation completion</div>
                  <div class="soc-progress-bar"><span style="width: 68%;"></span></div>
                </div>
              </div>
              <div class="soc-event">
                <div class="soc-event-top">
                  <span class="soc-badge severity-medium">Medium severity</span>
                  <span class="soc-badge">Reporting lane</span>
                </div>
                <h4 class="soc-event-title">Analyst report workflow shell</h4>
                <p class="soc-event-copy">
                  Establish reusable UI patterns for evidence summaries, MITRE mapping, and executive outputs.
                </p>
                <div class="soc-inline-list">
                  <span>Owner: Frontend</span>
                  <span>State: Planned</span>
                  <span>Focus: Layout system</span>
                </div>
              </div>
            </div>
          </div>
          <div class="soc-stack">
            <div class="soc-card glow">
              <div class="soc-card-label">Runtime posture</div>
        """
    )

    render_stat_list(
        [
            ("Application", config.app_name),
            ("Environment", config.environment),
            ("Debug mode", str(config.debug)),
            ("Allowed types", ", ".join(config.allowed_upload_types).upper()),
        ]
    )

    render_html_block(
        """
              <div class="soc-footer">Structured logging is enabled and writes JSON output to the configured log directory.</div>
            </div>
            <div class="soc-card">
              <div class="soc-card-label">Roadmap focus</div>
              <ul class="soc-list">
                <li><span>Alert normalization and validation</span><strong>Active</strong></li>
                <li><span>Analyst workflow orchestration</span><strong>Queued</strong></li>
                <li><span>Secure AI service boundaries</span><strong>Planned</strong></li>
                <li><span>Report generation and evidence capture</span><strong>Planned</strong></li>
              </ul>
            </div>
          </div>
        </div>
        """
    )
    render_shell_end()
