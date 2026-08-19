"""Purpose: Build and expose the FastAPI application instance."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.v1.router import api_router
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

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
