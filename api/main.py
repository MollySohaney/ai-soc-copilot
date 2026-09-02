"""Purpose: Build and expose the FastAPI application instance."""

from __future__ import annotations

import re
import uuid

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
from backend.audit.context import (
    AuditRequestContext,
    reset_audit_request_context,
    set_audit_request_context,
)
from config.settings import load_config


def create_app() -> FastAPI:
    """Construct the configured FastAPI application.

    Returns:
        The configured FastAPI application instance.
    """
    settings = load_config()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_audit_request_context(request: Request, call_next):  # noqa: ANN001, ANN202
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id
            if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_request_id)
            else str(uuid.uuid4())
        )
        token = set_audit_request_context(
            AuditRequestContext(
                request_id=request_id,
                source_ip=request.client.host if request.client else None,
                method=request.method,
                path=request.url.path[:500],
            )
        )
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            reset_audit_request_context(token)

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
