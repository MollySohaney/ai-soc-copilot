"""Purpose: Enforce authenticated opaque bearer sessions for protected routes."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.audit import AuditService
from backend.security.auth import AuthenticatedPrincipal, AuthenticationError, authenticate_session
from backend.security.rbac import AuthorizationDenied, Permission, require_user_permission
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


def require_permission(permission: Permission):  # noqa: ANN201
    """Build a FastAPI dependency backed by the central permission service."""

    def dependency(
        principal: AuthenticatedPrincipal = Depends(require_authenticated_user),
        db: Session = Depends(get_db),
    ) -> AuthenticatedPrincipal:
        try:
            require_user_permission(principal.user, permission)
        except AuthorizationDenied as error:
            AuditService(db).record(
                action="authorization.denied",
                outcome="denied",
                actor=principal.user,
                target_type="api_route",
                details={"permission": permission.value},
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permission.",
            ) from error
        return principal

    return dependency
