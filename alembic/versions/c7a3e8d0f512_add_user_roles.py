"""add user roles

Revision ID: c7a3e8d0f512
Revises: b6f2a7c9d401
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a3e8d0f512"
down_revision: Union[str, None] = "b6f2a7c9d401"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

role_enum = sa.Enum(
    "viewer",
    "analyst",
    "detection_engineer",
    "admin",
    name="roleenum",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", role_enum, server_default="viewer", nullable=False),
    )
    op.alter_column("users", "role", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "role")
