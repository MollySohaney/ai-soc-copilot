"""Purpose: Provide typed local authentication API operations."""

from __future__ import annotations

import httpx

from api.schemas.auth import LoginResponse, UserRead
from api_client.http import _request, get_default_client


def login(
    username: str, password: str, *, client: httpx.Client | None = None
) -> LoginResponse:
    """Exchange local credentials for one opaque bearer session."""
    response = _request(
        client or get_default_client(),
        "POST",
        "/auth/login",
        json={"username": username, "password": password},
    )
    return LoginResponse.model_validate(response.json())


def get_current_user(*, client: httpx.Client | None = None) -> UserRead:
    """Validate the current session and return safe user fields."""
    response = _request(client or get_default_client(), "GET", "/auth/me")
    return UserRead.model_validate(response.json())


def logout(*, client: httpx.Client | None = None) -> None:
    """Revoke the current opaque bearer session."""
    _request(client or get_default_client(), "POST", "/auth/logout")
