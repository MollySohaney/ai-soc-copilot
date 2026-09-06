"""Purpose: Define and enforce the application's server-side permission matrix."""

from __future__ import annotations

import enum

from db.models.user import RoleEnum, User


class Permission(str, enum.Enum):
    """Name stable capabilities instead of scattering role checks."""

    READ_SOC = "read_soc"
    MUTATE_INVESTIGATIONS = "mutate_investigations"
    REQUEST_AI = "request_ai"
    MANAGE_DETECTIONS = "manage_detections"
    OPERATE_INTEGRATIONS = "operate_integrations"
    MANAGE_USERS = "manage_users"
    READ_AUDIT = "read_audit"


_VIEW_PERMISSIONS = frozenset({Permission.READ_SOC})
ROLE_PERMISSIONS: dict[RoleEnum, frozenset[Permission]] = {
    RoleEnum.VIEWER: _VIEW_PERMISSIONS,
    RoleEnum.ANALYST: _VIEW_PERMISSIONS
    | frozenset({Permission.MUTATE_INVESTIGATIONS, Permission.REQUEST_AI}),
    RoleEnum.DETECTION_ENGINEER: _VIEW_PERMISSIONS
    | frozenset({Permission.MANAGE_DETECTIONS}),
    RoleEnum.ADMIN: frozenset(Permission),
}


class AuthorizationDenied(PermissionError):
    """Represent a server-side permission denial without target details."""


def role_has_permission(role: RoleEnum, permission: Permission) -> bool:
    """Return whether the central matrix grants a capability to a role."""
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_user_permission(user: User, permission: Permission) -> None:
    """Reject inactive users and roles lacking the requested capability."""
    if not user.is_active or not role_has_permission(user.role, permission):
        raise AuthorizationDenied("Insufficient permission.")
