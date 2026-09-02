"""Purpose: Apply identity-aware rate and concurrency limits to costly routes."""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.dependencies.auth import require_authenticated_user
from api.schemas.auth import LoginRequest
from backend.audit import AuditService
from backend.security.abuse_limiter import AbuseLimiter, get_abuse_limiter
from backend.security.auth import AuthenticatedPrincipal
from config.settings import AppConfig, load_config
from db.session import get_db


def _reject(
    *, db: Session, action: str, retry_after: int, principal: AuthenticatedPrincipal | None
) -> None:
    AuditService(db).record(
        action="abuse_limit.denied",
        outcome="denied",
        actor=principal.user if principal else None,
        target_type="api_operation",
        target_id=action,
        details={"retry_after_seconds": retry_after},
    )
    db.commit()
    raise HTTPException(
        status_code=429,
        detail="Request limit exceeded. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


def require_abuse_control(scope: str):  # noqa: ANN201
    """Build a dependency holding a per-user concurrency lease through response creation."""

    def dependency(
        principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
        db: Session = Depends(get_db),
        config: AppConfig = Depends(load_config),
        limiter: AbuseLimiter = Depends(get_abuse_limiter),
    ) -> Iterator[None]:
        key = limiter.key(scope=scope, identity=f"user:{principal.user.id}")
        lease, retry_after = limiter.acquire(
            key,
            max_requests=getattr(config, f"{scope}_rate_limit"),
            window_seconds=config.abuse_rate_window_seconds,
            max_concurrent=getattr(config, f"{scope}_concurrency_limit"),
        )
        if lease is None:
            _reject(
                db=db, action=scope, retry_after=retry_after, principal=principal
            )
        try:
            yield
        finally:
            lease.release()

    return dependency


def require_login_abuse_control(
    request: Request,
    payload: LoginRequest,
    db: Session = Depends(get_db),
    config: AppConfig = Depends(load_config),
    limiter: AbuseLimiter = Depends(get_abuse_limiter),
) -> Iterator[None]:
    """Bound all login attempts by hashed source-and-username identity."""
    client_host = request.client.host if request.client else "unknown"
    identity = f"{client_host}|{payload.username.strip().lower()}"
    key = limiter.key(scope="login", identity=identity)
    lease, retry_after = limiter.acquire(
        key,
        max_requests=config.login_rate_limit,
        window_seconds=config.abuse_rate_window_seconds,
        max_concurrent=config.login_concurrency_limit,
    )
    if lease is None:
        _reject(db=db, action="login", retry_after=retry_after, principal=None)
    try:
        yield
    finally:
        lease.release()
