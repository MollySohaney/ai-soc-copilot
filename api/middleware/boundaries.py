"""Purpose: Reject unsafe HTTP boundaries before endpoint body parsing."""

from __future__ import annotations

import re
import json
from collections import Counter
from urllib.parse import parse_qsl, unquote

from starlette.requests import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.errors import current_request_id, error_response

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")
_BODY_METHODS = {"POST", "PUT", "PATCH"}


class HttpBoundaryMiddleware:
    """Enforce paths, queries, media types, and body size before FastAPI parsing."""

    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self._app = app
        self._max_body_bytes = max_body_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        request = Request(scope)
        request_id = current_request_id(request)
        unsafe_message = self._unsafe_target(scope)
        if unsafe_message is not None:
            response = error_response(
                status_code=400, message=unsafe_message, request_id=request_id
            )
            await response(scope, receive, send)
            return

        method = str(scope.get("method", "GET")).upper()
        content_length = self._content_length(scope)
        if content_length is not None and content_length > self._max_body_bytes:
            response = error_response(
                status_code=413,
                message="Request body exceeds the configured limit.",
                request_id=request_id,
            )
            await response(scope, receive, send)
            return
        if method in _BODY_METHODS and (content_length is None or content_length > 0):
            media_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
            if media_type != "application/json":
                response = error_response(
                    status_code=415,
                    message="Content-Type must be application/json.",
                    request_id=request_id,
                )
                await response(scope, receive, send)
                return

        if method not in _BODY_METHODS:
            await self._app(scope, receive, send)
            return

        body = bytearray()
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > self._max_body_bytes:
                response = error_response(
                    status_code=413,
                    message="Request body exceeds the configured limit.",
                    request_id=request_id,
                )
                await response(scope, receive, send)
                return
            more_body = bool(message.get("more_body", False))

        if body:
            try:
                json.loads(body, object_pairs_hook=self._reject_duplicate_json_keys)
            except _DuplicateJsonKey:
                response = error_response(
                    status_code=400,
                    message="Duplicate JSON fields are not allowed.",
                    request_id=request_id,
                )
                await response(scope, receive, send)
                return
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self._app(scope, replay, send)

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    parsed = int(value)
                except ValueError:
                    return None
                return max(0, parsed)
        return None

    @staticmethod
    def _unsafe_target(scope: Scope) -> str | None:
        raw_path = scope.get("raw_path", b"").decode("latin-1", errors="replace")
        decoded_path = unquote(raw_path)
        if (
            len(raw_path) > 2048
            or len(scope.get("query_string", b"")) > 4096
            or _CONTROL_CHARACTERS.search(decoded_path)
            or "\\" in decoded_path
            or ".." in decoded_path.split("/")
        ):
            return "Unsafe request path."
        raw_query = scope.get("query_string", b"").decode("utf-8", errors="replace")
        pairs = parse_qsl(raw_query, keep_blank_values=True)
        counts = Counter(key for key, _value in pairs)
        if any(count > 1 for count in counts.values()):
            return "Duplicate query parameters are not allowed."
        if any(
            _CONTROL_CHARACTERS.search(key) or _CONTROL_CHARACTERS.search(value)
            for key, value in pairs
        ):
            return "Control characters are not allowed in query parameters."
        return None

    @staticmethod
    def _reject_duplicate_json_keys(pairs):  # noqa: ANN001, ANN202
        result = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateJsonKey(key)
            result[key] = value
        return result


class _DuplicateJsonKey(ValueError):
    """Signal an ambiguous JSON object without retaining its submitted value."""
