"""Purpose: Define safe Admin-only local user management contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from api.schemas.auth import UserRead
from db.models.user import RoleEnum


class AdminUserCreate(BaseModel):
    """Create one local identity without accepting password hashes."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=12, max_length=1024)
    role: RoleEnum = RoleEnum.VIEWER


class AdminUserUpdate(BaseModel):
    """Change only authorization and activation state."""

    model_config = ConfigDict(extra="forbid")

    role: RoleEnum | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_change(self) -> "AdminUserUpdate":
        """Reject empty Admin mutations."""
        if self.role is None and self.is_active is None:
            raise ValueError("At least one user field must be provided.")
        return self


class PaginatedUsers(BaseModel):
    """Return a bounded page of safe identity fields."""

    items: list[UserRead]
    total: int
    page: int
    page_size: int
    total_pages: int
