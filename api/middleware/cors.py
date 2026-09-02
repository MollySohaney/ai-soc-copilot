"""Purpose: Keep CORS denials inside the common JSON error boundary."""

from __future__ import annotations

from starlette.datastructures import Headers
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from api.errors import current_request_id, error_response


class SafeCORSMiddleware(CORSMiddleware):
    """Return the documented error contract for rejected preflight requests."""

    def preflight_response(self, request_headers: Headers) -> Response:
        response = super().preflight_response(request_headers)
        if response.status_code < 400:
            return response
        return error_response(
            status_code=response.status_code,
            message="CORS preflight request denied.",
            request_id=current_request_id(),
            code="cors_denied",
            headers=dict(response.headers),
        )
