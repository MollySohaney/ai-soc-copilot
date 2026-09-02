"""Purpose: Create bounded, redacted, append-only security audit records."""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.audit.context import get_audit_request_context
from db.models import AuditEvent, User

_SECRET_KEY = re.compile(
    r"password|passwd|secret|token|api[_-]?key|authorization|cookie|csrf|private[_-]?key|hash",
    re.IGNORECASE,
)
_PROHIBITED_CONTENT_KEY = re.compile(
    r"raw[_-]?(event|payload|evidence)|prompt|system[_-]?instruction|user[_-]?content",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|cookie|csrf)\s*[:=]\s*[^\s,;]+"
)
_MAX_STRING_LENGTH = 1024
_MAX_COLLECTION_ITEMS = 100
_MAX_DEPTH = 6
_MAX_SERIALIZED_BYTES = 16_384


def sanitize_audit_value(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact forbidden fields and bound attacker-controlled values."""
    if _depth >= _MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                sanitized["_truncated"] = True
                break
            safe_key = str(key)[:128]
            if _SECRET_KEY.search(safe_key) or _PROHIBITED_CONTENT_KEY.search(safe_key):
                sanitized[safe_key] = "[REDACTED]"
            else:
                sanitized[safe_key] = sanitize_audit_value(item, _depth=_depth + 1)
        return sanitized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        items = list(value[:_MAX_COLLECTION_ITEMS])
        sanitized_items = [sanitize_audit_value(item, _depth=_depth + 1) for item in items]
        if len(value) > _MAX_COLLECTION_ITEMS:
            sanitized_items.append("[TRUNCATED]")
        return sanitized_items
    if isinstance(value, str):
        redacted = _SECRET_VALUE.sub(lambda match: f"{match.group(1)}=[REDACTED]", value)
        if len(redacted) > _MAX_STRING_LENGTH:
            return redacted[:_MAX_STRING_LENGTH] + "[TRUNCATED]"
        return redacted
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return normalized.astimezone(timezone.utc).isoformat()
    return str(value)[:_MAX_STRING_LENGTH]


def _bounded_dict(value: Mapping[str, Any] | None) -> dict | None:
    if value is None:
        return None
    sanitized = sanitize_audit_value(value)
    encoded = json.dumps(sanitized, sort_keys=True, default=str).encode("utf-8")
    if len(encoded) <= _MAX_SERIALIZED_BYTES:
        return sanitized
    return {"_truncated": True, "original_size_bytes": len(encoded)}


class AuditService:
    """Append audit rows to the caller's current database transaction."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def record(
        self,
        *,
        action: str,
        outcome: str,
        actor: User | None = None,
        actor_identifier: str | None = None,
        actor_type: str | None = None,
        target_type: str | None = None,
        target_id: str | int | None = None,
        before_state: Mapping[str, Any] | None = None,
        after_state: Mapping[str, Any] | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> AuditEvent:
        """Stage one immutable event without committing the surrounding transaction."""
        if outcome not in {"succeeded", "failed", "denied"}:
            raise ValueError("Audit outcome must be succeeded, failed, or denied.")
        context = get_audit_request_context()
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=actor.id if actor is not None else None,
            actor_type=actor_type or ("user" if actor is not None else "anonymous"),
            actor_identifier=str(
                sanitize_audit_value(actor.username if actor is not None else actor_identifier)
            )[:255]
            if (actor is not None or actor_identifier is not None)
            else None,
            action=action[:100],
            target_type=target_type[:100] if target_type else None,
            target_id=str(target_id)[:255] if target_id is not None else None,
            outcome=outcome,
            request_id=context.request_id if context else None,
            source_ip=context.source_ip if context else None,
            source_context=_bounded_dict(
                {"method": context.method, "path": context.path} if context else None
            ),
            before_state=_bounded_dict(before_state),
            after_state=_bounded_dict(after_state),
            details=_bounded_dict(details),
        )
        self._db.add(event)
        return event
