"""add append-only AI analysis records

Revision ID: 9d2f4a6b7c81
Revises: 6c4d2e8f1a90
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d2f4a6b7c81"
down_revision: Union[str, None] = "6c4d2e8f1a90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_type", sa.String(length=100), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=True),
        sa.Column("case_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=False),
        sa.Column("response_schema_version", sa.String(length=50), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("evidence_refs", sa.JSON(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("rate_limit_remaining", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "alert_id IS NOT NULL OR case_id IS NOT NULL",
            name="ck_ai_analyses_has_scope",
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], name="fk_ai_analyses_alert_id_alerts"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], name="fk_ai_analyses_case_id_cases"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_analyses")),
    )
    op.create_index(
        "ix_ai_analyses_alert_id_created_at", "ai_analyses", ["alert_id", "created_at"]
    )
    op.create_index(
        "ix_ai_analyses_case_id_created_at", "ai_analyses", ["case_id", "created_at"]
    )
    op.create_index("ix_ai_analyses_status", "ai_analyses", ["status"])
    op.create_index("ix_ai_analyses_analysis_type", "ai_analyses", ["analysis_type"])


def downgrade() -> None:
    op.drop_index("ix_ai_analyses_analysis_type", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_status", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_case_id_created_at", table_name="ai_analyses")
    op.drop_index("ix_ai_analyses_alert_id_created_at", table_name="ai_analyses")
    op.drop_table("ai_analyses")
