"""Purpose: Provide a framework-agnostic HTTP transport for the SOC API client."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx

from config.settings import load_config


class ApiClientError(Exception):
    """Represent a failure calling the SOC API, whether from a transport or HTTP error."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        """Initialize the error with a human-readable message and optional HTTP context.

        Args:
            message: A human-readable summary of the failure.
            status_code: The HTTP status code returned by the API, if any.
            detail: The `detail` field from the API's JSON error body, if any.
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


def build_client(base_url: str, *, timeout: float = 10.0) -> httpx.Client:
    """Build an httpx client configured to call the SOC API.

    Args:
        base_url: The base URL to prefix onto every request path, e.g.
            "http://localhost:8000/api/v1".
        timeout: The request timeout, in seconds.

    Returns:
        A configured httpx client.
    """
    return httpx.Client(base_url=base_url, timeout=timeout)


@lru_cache(maxsize=1)
def get_default_client() -> httpx.Client:
    """Return the shared default client, built from application settings.

    Every resource function accepts an injectable `client` argument for testing;
    this is only used when a caller does not supply one.

    Returns:
        A lazily-constructed, process-wide httpx client for the SOC API.
    """
    settings = load_config()
    base_url = f"{settings.api_base_url}/api/{settings.api_version}"
    return build_client(base_url)


def _extract_detail(response: httpx.Response) -> str | None:
    """Pull the FastAPI `detail` field out of an error response body, if present.

    Args:
        response: The HTTP response to inspect.

    Returns:
        The detail string, or None if the body is not JSON or has no `detail` field.
    """
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, dict):
        detail = body.get("detail")
        if isinstance(detail, str):
            return detail
    return None


def _request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> httpx.Response:
    """Issue an HTTP request through the given client, normalizing failures.

    Args:
        client: The httpx client to issue the request with.
        method: The HTTP method, e.g. "GET", "PATCH", "POST", "DELETE".
        path: The request path, relative to the client's configured base URL.
        **kwargs: Additional keyword arguments forwarded to `httpx.Client.request`.

    Returns:
        The successful HTTP response.

    Raises:
        ApiClientError: If the request fails to connect, or the API returns a
            non-2xx status code.
    """
    try:
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
    except httpx.RequestError as exc:
        raise ApiClientError(f"Failed to reach the SOC API: {exc}") from exc
    except httpx.HTTPStatusError as exc:
        detail = _extract_detail(exc.response)
        message = detail or f"SOC API request failed with status {exc.response.status_code}"
        raise ApiClientError(
            message, status_code=exc.response.status_code, detail=detail
        ) from exc
    return response


def clean_params(**kwargs: Any) -> dict[str, Any]:
    """Drop unset (None) values from a set of query parameters.

    Args:
        **kwargs: Candidate query parameters, some of which may be None.

    Returns:
        Only the parameters with a non-None value.
    """
    return {key: value for key, value in kwargs.items() if value is not None}
