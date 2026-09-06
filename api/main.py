"""Purpose: Build and expose the FastAPI application instance."""

from __future__ import annotations

import re
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from api.errors import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from api.middleware import HttpBoundaryMiddleware, SafeCORSMiddleware
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
        SafeCORSMiddleware,
        allow_origins=settings.frontend_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(HttpBoundaryMiddleware, max_body_bytes=settings.api_max_body_bytes)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

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
