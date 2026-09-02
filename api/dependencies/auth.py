"""Purpose: Enforce authenticated opaque bearer sessions for protected routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.security.auth import AuthenticatedPrincipal, AuthenticationError, authenticate_session
from config.settings import AppConfig, load_config
from db.session import get_db

_BEARER = HTTPBearer(auto_error=False)


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_BEARER),
    db: Session = Depends(get_db),
    config: AppConfig = Depends(load_config),
) -> AuthenticatedPrincipal:
    """Return the authenticated principal or a generic bearer challenge."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _authentication_error()
    try:
        return authenticate_session(db, access_token=credentials.credentials, config=config)
    except AuthenticationError as error:
        raise _authentication_error() from error


def _authentication_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
