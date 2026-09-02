"""Purpose: Enforce Admin authorization around local identity mutations."""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.security.auth import create_user
from backend.security.rbac import Permission, require_user_permission
from db.models import AuthSession, RoleEnum, User


class UserNotFoundError(LookupError):
    """Represent a requested user that does not exist."""


class DuplicateUserError(ValueError):
    """Represent a normalized username collision."""


class FinalAdminError(ValueError):
    """Protect the final active Admin from demotion or disablement."""


class UserAdminService:
    """Provide permission-checked user administration operations."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_users(
        self, *, actor: User, page: int, page_size: int
    ) -> tuple[list[User], int, int]:
        """Return a bounded user page after an Admin service-layer check."""
        require_user_permission(actor, Permission.MANAGE_USERS)
        total = self._db.scalar(select(func.count()).select_from(User)) or 0
        users = list(
            self._db.scalars(
                select(User)
                .order_by(User.username.asc(), User.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return users, total, math.ceil(total / page_size) if total else 0

    def create_user(
        self, *, actor: User, username: str, password: str, role: RoleEnum
    ) -> User:
        """Create a least-privilege user without accepting a precomputed hash."""
        require_user_permission(actor, Permission.MANAGE_USERS)
        user, created = create_user(
            self._db, username=username, password=password, role=role
        )
        if not created:
            raise DuplicateUserError("Username already exists.")
        self._db.commit()
        self._db.refresh(user)
        return user

    def update_user(
        self,
        *,
        actor: User,
        user_id: int,
        role: RoleEnum | None,
        is_active: bool | None,
    ) -> User:
        """Change role/activation atomically and revoke affected sessions."""
        require_user_permission(actor, Permission.MANAGE_USERS)
        target = self._db.get(User, user_id)
        if target is None:
            raise UserNotFoundError("User not found.")

        removes_active_admin = (
            target.role == RoleEnum.ADMIN
            and target.is_active
            and (role not in (None, RoleEnum.ADMIN) or is_active is False)
        )
        if removes_active_admin:
            active_admins = self._db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.role == RoleEnum.ADMIN, User.is_active.is_(True))
            )
            if (active_admins or 0) <= 1:
                raise FinalAdminError("The final active Admin cannot be changed.")

        role_changed = role is not None and role != target.role
        active_changed = is_active is not None and is_active != target.is_active
        if role is not None:
            target.role = role
        if is_active is not None:
            target.is_active = is_active
        if role_changed or active_changed:
            target.updated_at = datetime.now(timezone.utc)
            self._revoke_sessions(user_id=target.id)
        self._db.commit()
        self._db.refresh(target)
        return target

    def revoke_sessions(self, *, actor: User, user_id: int) -> None:
        """Revoke all live sessions for one user after an Admin check."""
        require_user_permission(actor, Permission.MANAGE_USERS)
        if self._db.get(User, user_id) is None:
            raise UserNotFoundError("User not found.")
        self._revoke_sessions(user_id=user_id)
        self._db.commit()

    def _revoke_sessions(self, *, user_id: int) -> None:
        self._db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
