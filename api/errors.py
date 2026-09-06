"""Purpose: Return one safe, correlation-aware API error contract."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.audit.context import get_audit_request_context


_STATUS_CODES = {
    400: "bad_request",
    401: "authentication_required",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "request_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    502: "upstream_unavailable",
    503: "service_unavailable",
    504: "upstream_timeout",
}


def current_request_id(request: Request | None = None) -> str:
    """Return the validated request correlation identifier."""
    context = get_audit_request_context()
    if context is not None:
        return context.request_id
    if request is not None:
        return request.headers.get("X-Request-ID", "unavailable")[:64]
    return "unavailable"


def error_response(
    *,
    status_code: int,
    message: str,
    request_id: str,
    code: str | None = None,
    details: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the sole public API error representation."""
    error: dict[str, Any] = {
        "code": code or _STATUS_CODES.get(status_code, "internal_error"),
        "message": message,
        "request_id": request_id,
    }
    if details:
        error["details"] = details
    response_headers = {"X-Request-ID": request_id, **(headers or {})}
    return JSONResponse(
        status_code=status_code,
        content={"error": error},
        headers=response_headers,
    )


def _validation_details(error: RequestValidationError) -> list[dict[str, Any]]:
    """Expose field locations and classes without echoing attacker input."""
    return [
        {
            "location": [str(part) for part in item.get("loc", ())],
            "code": str(item.get("type", "invalid"))[:100],
            "message": "Invalid value.",
        }
        for item in error.errors()[:50]
    ]


async def http_exception_handler(request: Request, error: HTTPException) -> JSONResponse:
    """Translate explicit HTTP failures into the common safe schema."""
    status_code = error.status_code
    message = str(error.detail) if isinstance(error.detail, str) else "Request failed."
    if status_code >= 500:
        message = {
            502: "An upstream service is unavailable.",
            503: "Service temporarily unavailable.",
            504: "An upstream service timed out.",
        }.get(status_code, "Internal server error.")
    return error_response(
        status_code=status_code,
        message=message,
        request_id=current_request_id(request),
        headers=dict(error.headers or {}),
    )


async def validation_exception_handler(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    """Return bounded validation metadata without submitted values."""
    return error_response(
        status_code=422,
        message="Request validation failed.",
        request_id=current_request_id(request),
        details=_validation_details(error),
    )


async def unhandled_exception_handler(request: Request, _error: Exception) -> JSONResponse:
    """Prevent stack traces and internal exception details from crossing the API boundary."""
    return error_response(
        status_code=500,
        message="Internal server error.",
        request_id=current_request_id(request),
    )
