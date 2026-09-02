"""Purpose: Expose local login, logout, and current-session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from api.dependencies.auth import require_authenticated_user
from api.schemas.auth import LoginRequest, LoginResponse, UserRead
from backend.security.auth import (
    AuthenticatedPrincipal,
    authenticate_user,
    issue_session,
    revoke_session,
)
from backend.security.login_limiter import LoginAttemptLimiter, get_login_limiter
from config.settings import AppConfig, load_config
from db.session import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    config: AppConfig = Depends(load_config),
    limiter: LoginAttemptLimiter = Depends(get_login_limiter),
) -> LoginResponse:
    """Authenticate a local user and issue one revocable opaque session."""
    client_host = request.client.host if request.client is not None else "unknown"
    limit_key = limiter.key(client_host=client_host, username=payload.username)
    if not limiter.is_allowed(
        limit_key,
        max_attempts=config.auth_login_max_attempts,
        window_seconds=config.auth_login_window_seconds,
    ):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(config.auth_login_window_seconds)},
        )

    user = authenticate_user(
        db, username=payload.username, password=payload.password.get_secret_value()
    )
    if user is None:
        limiter.record_failure(limit_key, window_seconds=config.auth_login_window_seconds)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    limiter.clear(limit_key)
    issued = issue_session(db, user=user, config=config)
    db.commit()
    return LoginResponse(
        access_token=issued.access_token,
        expires_at=issued.session.absolute_expires_at,
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def current_user(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
) -> UserRead:
    """Return safe identity fields for a valid session."""
    return UserRead.model_validate(principal.user)


@router.post("/logout", status_code=204)
def logout(
    principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> None:
    """Revoke the caller's current session."""
    revoke_session(db, session=principal.session)
