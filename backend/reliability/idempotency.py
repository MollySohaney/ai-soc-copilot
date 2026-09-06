"""Purpose: Enforce bounded actor-scoped idempotency without caching failures or secrets."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.models import IdempotencyRecord


class IdempotencyConflict(ValueError):
    """Represent key reuse with a different payload or an in-flight request."""


class IdempotencyReplay:
    """Represent a previously completed safe response."""

    def __init__(self, status_code: int, body: dict[str, Any]) -> None:
        self.status_code = status_code
        self.body = body


def digest_payload(value: Any) -> str:
    """Hash canonical JSON without retaining submitted secrets."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class IdempotencyService:
    """Reserve and complete operation-scoped keys with bounded retention."""

    def __init__(self, db: Session, *, retention_hours: int = 24) -> None:
        self._db = db
        self._retention = max(1, retention_hours)

    def begin(
        self, *, actor_user_id: int, operation: str, key: str, payload: Any
    ) -> IdempotencyRecord | IdempotencyReplay | None:
        """Return replay/None or reserve a key; never cache authorization failures."""
        if not key or len(key) > 128:
            raise IdempotencyConflict("Idempotency-Key must contain 1-128 characters.")
        key_digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        request_digest = digest_payload(payload)
        existing = self._db.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.actor_user_id == actor_user_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key_digest == key_digest,
            )
        )
        if existing is not None:
            expires_at = existing.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                self._db.delete(existing)
                self._db.flush()
            elif existing.request_digest != request_digest:
                raise IdempotencyConflict("Idempotency-Key was reused with a different request.")
            elif existing.status == "completed" and existing.response_body is not None:
                return IdempotencyReplay(existing.response_status or 200, existing.response_body)
            else:
                raise IdempotencyConflict("An equivalent request is already in progress.")
        record = IdempotencyRecord(
            actor_user_id=actor_user_id,
            operation=operation[:100],
            key_digest=key_digest,
            request_digest=request_digest,
            status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=self._retention),
        )
        self._db.add(record)
        try:
            self._db.flush()
        except IntegrityError as error:
            self._db.rollback()
            raise IdempotencyConflict("An equivalent request is already in progress.") from error
        self._db.commit()
        return record

    def complete(self, record: IdempotencyRecord, *, status_code: int, body: dict[str, Any]) -> None:
        """Cache only a safe successful response body."""
        if status_code >= 400:
            return
        record.status = "completed"
        record.response_status = status_code
        record.response_body = body
        self._db.commit()

    def abandon(self, record: IdempotencyRecord) -> None:
        """Remove a reservation when the protected operation fails before success."""
        self._db.delete(record)
        self._db.commit()


__all__ = ["IdempotencyConflict", "IdempotencyReplay", "IdempotencyService", "digest_payload"]
