"""Purpose: Define non-secret authentication API contracts."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from db.models.user import RoleEnum


class LoginRequest(BaseModel):
    """Accept a bounded local username and secret password."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=1024)


class UserRead(BaseModel):
    """Expose safe identity fields only."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: RoleEnum
    is_active: bool


class LoginResponse(BaseModel):
    """Return the opaque token exactly at successful login."""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead
