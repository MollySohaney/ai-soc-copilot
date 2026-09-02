"""Purpose: Expose Admin-only local user and session management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.dependencies.auth import require_permission
from api.schemas.admin import AdminUserCreate, AdminUserUpdate, PaginatedUsers
from api.schemas.auth import UserRead
from backend.security.auth import AuthenticatedPrincipal
from backend.security.rbac import Permission
from backend.services.user_admin_service import (
    DuplicateUserError,
    FinalAdminError,
    UserAdminService,
    UserNotFoundError,
)
from db.session import get_db

router = APIRouter(
    prefix="/admin/users",
    tags=["admin"],
    dependencies=[Depends(require_permission(Permission.MANAGE_USERS))],
)


def _service_error(error: Exception) -> HTTPException:
    if isinstance(error, UserNotFoundError):
        return HTTPException(status_code=404, detail="User not found.")
    if isinstance(error, DuplicateUserError):
        return HTTPException(status_code=409, detail="Username already exists.")
    if isinstance(error, FinalAdminError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=400, detail="User operation failed.")


@router.get("", response_model=PaginatedUsers)
def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.MANAGE_USERS)),
    db: Session = Depends(get_db),
) -> PaginatedUsers:
    """List local users without credential/session material."""
    items, total, total_pages = UserAdminService(db).list_users(
        actor=principal.user, page=page, page_size=page_size
    )
    return PaginatedUsers(
        items=[UserRead.model_validate(user) for user in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post("", response_model=UserRead, status_code=201)
def create_local_user(
    payload: AdminUserCreate,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.MANAGE_USERS)),
    db: Session = Depends(get_db),
) -> UserRead:
    """Create a local user with an explicit role."""
    try:
        user = UserAdminService(db).create_user(
            actor=principal.user,
            username=payload.username,
            password=payload.password.get_secret_value(),
            role=payload.role,
        )
    except (DuplicateUserError, ValueError) as error:
        raise _service_error(error) from error
    return UserRead.model_validate(user)


@router.patch("/{user_id}", response_model=UserRead)
def update_local_user(
    user_id: int,
    payload: AdminUserUpdate,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.MANAGE_USERS)),
    db: Session = Depends(get_db),
) -> UserRead:
    """Change a role or activation state and revoke existing sessions."""
    try:
        user = UserAdminService(db).update_user(
            actor=principal.user,
            user_id=user_id,
            role=payload.role,
            is_active=payload.is_active,
        )
    except (UserNotFoundError, FinalAdminError) as error:
        raise _service_error(error) from error
    return UserRead.model_validate(user)


@router.post("/{user_id}/revoke-sessions", status_code=status.HTTP_204_NO_CONTENT)
def revoke_local_user_sessions(
    user_id: int,
    principal: AuthenticatedPrincipal = Depends(require_permission(Permission.MANAGE_USERS)),
    db: Session = Depends(get_db),
) -> None:
    """Revoke all current sessions for a local user."""
    try:
        UserAdminService(db).revoke_sessions(actor=principal.user, user_id=user_id)
    except UserNotFoundError as error:
        raise _service_error(error) from error
