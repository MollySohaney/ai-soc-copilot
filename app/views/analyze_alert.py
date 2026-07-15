"""Purpose: Render the placeholder alert upload and preview workflow."""

from __future__ import annotations

import streamlit as st

from ..components.layout import render_page_header
from backend.services.upload_service import AlertUploadService
from config.settings import AppConfig


def render(config: AppConfig, upload_service: AlertUploadService) -> None:
    """Render the Analyze Alert page.

    Args:
        config: Application configuration.
        upload_service: Service that handles upload validation and parsing.
    """
    render_page_header(
        title="Analyze Alert",
        description=(
            "Upload alert evidence files to validate the ingestion path. "
            "AI analysis is intentionally not implemented yet."
        ),
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
        st.write("Select a JSON, CSV, or TXT file to preview how the ingestion layer behaves.")
        return

    result = upload_service.process_upload(
        file_name=uploaded_file.name,
        content=uploaded_file.getvalue(),
    )

    if not result.is_valid:
        st.error(result.message)
        return

    st.success(result.message)
    st.subheader("File Metadata")
    st.json(result.preview.metadata)

    st.subheader("Preview")
    if result.preview.preview_rows:
        st.dataframe(result.preview.preview_rows, use_container_width=True)
    else:
        st.code(result.preview.text_preview or "No preview available.", language="text")
