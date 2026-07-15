"""Purpose: Render the placeholder alert upload and preview workflow."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_html_block, render_stat_list
from ..components.theme import render_shell_end, render_shell_start
from backend.services.upload_service import AlertUploadService
from config.settings import AppConfig


def render(config: AppConfig, upload_service: AlertUploadService) -> None:
    """Render the Analyze Alert page.

    Args:
        config: Application configuration.
        upload_service: Service that handles upload validation and parsing.
    """
    render_shell_start(
        title="Analyze Alert",
        description=(
            "Upload alert evidence to exercise the ingestion, validation, and preview path. "
            "AI-assisted interpretation is intentionally deferred."
        ),
        breadcrumb="SOC workspace / intake",
        status_chips=[
            ("Accepted", ", ".join(config.allowed_upload_types).upper()),
            ("Max size", f"{config.max_upload_size_mb} MB"),
        ],
    )
    render_html_block('<div class="soc-grid"><div class="soc-stack"><div class="soc-card glow">')
    render_html_block(
        """
        <div class="soc-card-label">Alert intake</div>
        <h3 class="soc-card-title">Evidence upload staging area</h3>
        <p class="soc-card-subtitle">
          Use the sample files in the <code>data/</code> directory to verify how the parser and
          validation layer behave before model-backed analysis exists.
        </p>
        """
    )

    uploaded_file = st.file_uploader(
        label="Upload an alert artifact",
        type=config.allowed_upload_types,
        help=(
            "Supported file types: "
            f"{', '.join(config.allowed_upload_types).upper()} | "
            f"Max size: {config.max_upload_size_mb} MB"
        ),
    )

    if uploaded_file is None:
        render_html_block("</div>")
        render_html_block('<div class="soc-card"><div class="soc-card-label">Recommended fixtures</div>')
        render_stat_list(
            [
                ("JSON", "data/sample_alert.json"),
                ("CSV", "data/sample_alerts.csv"),
                ("TXT", "data/sample_alert.txt"),
            ]
        )
        render_html_block(
            """
            <div class="soc-footer">
              Select a JSON, CSV, or TXT file to preview normalized metadata and the initial evidence view.
            </div>
            </div>
            </div>
            <div class="soc-stack">
              <div class="soc-card glow">
                <div class="soc-card-label">Ingestion policy</div>
            """
        )
        render_stat_list(
            [
                ("UTF-8 required", "Yes"),
                ("Extension allowlist", ", ".join(config.allowed_upload_types).upper()),
                ("Max upload size", f"{config.max_upload_size_mb} MB"),
                ("AI processing", "Disabled"),
            ]
        )
        render_html_block(
            """
                <div class="soc-footer">Uploads are validated before parsing and never leave the local session in this scaffold.</div>
              </div>
            </div>
            </div>
            """
        )
        render_shell_end()
        return

    result = upload_service.process_upload(
        file_name=uploaded_file.name,
        content=uploaded_file.getvalue(),
    )

    if not result.is_valid:
        st.error(result.message)
        render_html_block("</div>")
        render_html_block('<div class="soc-stack"><div class="soc-card"><div class="soc-card-label">Validation status</div><div class="soc-note">Correct the upload issue and try again.</div></div></div></div>')
        render_shell_end()
        return

    st.success(result.message)
    render_html_block("</div>")
    render_html_block('<div class="soc-card"><div class="soc-card-label">File metadata</div>')
    render_stat_list(
        [(str(key).replace("_", " ").title(), str(value)) for key, value in result.preview.metadata.items()]
    )
    render_html_block("</div></div><div class=\"soc-stack\"><div class=\"soc-card glow\"><div class=\"soc-card-label\">Preview</div>")
    if result.preview.preview_rows:
        st.dataframe(result.preview.preview_rows, use_container_width=True)
    else:
        st.code(result.preview.text_preview or "No preview available.", language="text")
    render_html_block("</div></div></div>")
    render_shell_end()
