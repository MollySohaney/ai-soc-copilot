"""Purpose: Carry safe request correlation metadata into audit records."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class AuditRequestContext:
    """Store only bounded, non-secret request metadata."""

    request_id: str
    source_ip: str | None
    method: str
    path: str


_CONTEXT: ContextVar[AuditRequestContext | None] = ContextVar(
    "audit_request_context", default=None
)


def set_audit_request_context(context: AuditRequestContext) -> Token:
    """Set request metadata and return the reset token."""
    return _CONTEXT.set(context)


def reset_audit_request_context(token: Token) -> None:
    """Restore the context that preceded one request."""
    _CONTEXT.reset(token)


def get_audit_request_context() -> AuditRequestContext | None:
    """Return metadata for the active request, if any."""
    return _CONTEXT.get()
