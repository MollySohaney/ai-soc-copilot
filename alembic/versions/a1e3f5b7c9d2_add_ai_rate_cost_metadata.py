"""add AI rate and cost metadata

Revision ID: a1e3f5b7c9d2
Revises: 9d2f4a6b7c81
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1e3f5b7c9d2"
down_revision: Union[str, None] = "9d2f4a6b7c81"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_analyses", sa.Column("rate_limit_remaining", sa.Integer(), nullable=True))
    op.add_column("ai_analyses", sa.Column("estimated_cost_usd", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_analyses", "estimated_cost_usd")
    op.drop_column("ai_analyses", "rate_limit_remaining")
