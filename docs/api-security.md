# API boundary and abuse controls

The FastAPI service accepts JSON request bodies only. `API_MAX_BODY_BYTES`
defaults to 1 MiB and is enforced while receiving the request, before FastAPI or
Pydantic buffers and parses it. Duplicate query keys, decoded traversal segments,
backslashes, and control characters in request targets are rejected. Every error
uses this contract:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "request_id": "a-safe-correlation-id",
    "details": []
  }
}
```

Validation details never echo submitted values. Server and upstream failures use
generic messages. `X-Request-ID` is returned on success and failure. Callers may
supply 1–64 ASCII letters, digits, dots, underscores, or hyphens; other values are
replaced.

`FRONTEND_ORIGIN` is a comma-separated allowlist. CORS permits only `GET`, `POST`,
`PATCH`, `DELETE`, and preflight `OPTIONS`, with `Authorization`, `Content-Type`,
and `X-Request-ID`. Cookie credentials and wildcard origins/headers/methods are
disabled.

## Expensive operations

Login, AI requests, manual ingestion, and manual detection operations have
separate rate and in-flight concurrency limits. Authenticated operations key on
the server-validated user ID. Login keys hash the socket peer address and
normalized username; forwarded IP headers are intentionally ignored. A rejected
request returns `429`, `Retry-After`, the common error body, and an audit event.

The defaults are documented in `.env.example`. These counters are intentionally
process-local for the local portfolio deployment. A multi-worker or distributed
deployment must replace `AbuseLimiter` with a shared atomic store such as Redis,
and must configure trusted-proxy handling before using forwarded client addresses.

## Files and exports

The current upload workflow is local to Streamlit; there is no HTTP upload or
export endpoint. Its validator still enforces a 255-character basename, repeated
URL-decoding checks, no traversal/control characters, configured extensions,
UTF-8 text, content signatures, NUL rejection, and size before parsing. Export
helpers generate attachment basenames and prefix spreadsheet formula cells. Any
future HTTP download must use these helpers, a server-selected content type, and a
server-generated `Content-Disposition` filename.
