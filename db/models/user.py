"""Purpose: Persist local users and revocable opaque authentication sessions."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base


class RoleEnum(str, enum.Enum):
    """Enumerate the supported least-privilege application roles."""

    VIEWER = "viewer"
    ANALYST = "analyst"
    DETECTION_ENGINEER = "detection_engineer"
    ADMIN = "admin"


class User(Base):
    """Represent one local application identity."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_username", "username", unique=True),)

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    role: Mapped[RoleEnum] = mapped_column(
        Enum(
            RoleEnum,
            values_callable=lambda roles: [role.value for role in roles],
            native_enum=False,
        ),
        nullable=False,
        default=RoleEnum.VIEWER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthSession(Base):
    """Persist only the digest and lifecycle metadata for an opaque bearer token."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index("ix_auth_sessions_token_hash", "token_hash", unique=True),
        Index("ix_auth_sessions_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_auth_sessions_absolute_expires_at", "absolute_expires_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")
