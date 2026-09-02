"""add append-only audit events

Revision ID: d8b4f9e1a623
Revises: c7a3e8d0f512
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8b4f9e1a623"
down_revision: Union[str, None] = "c7a3e8d0f512"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_identifier", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=100), nullable=True),
        sa.Column("target_id", sa.String(length=255), nullable=True),
        sa.Column("outcome", sa.String(length=20), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("source_context", sa.JSON(), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_events_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index("ix_audit_events_event_id", "audit_events", ["event_id"], unique=True)
    op.create_index("ix_audit_events_occurred_at", "audit_events", ["occurred_at"])
    op.create_index(
        "ix_audit_events_actor_user_id_occurred_at",
        "audit_events",
        ["actor_user_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_action_occurred_at",
        "audit_events",
        ["action", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_target_occurred_at",
        "audit_events",
        ["target_type", "target_id", "occurred_at"],
    )
    op.create_index(
        "ix_audit_events_outcome_occurred_at",
        "audit_events",
        ["outcome", "occurred_at"],
    )
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_append_only
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
            """
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS audit_events_append_only ON audit_events")
        op.execute("DROP FUNCTION IF EXISTS reject_audit_event_mutation()")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_events_outcome_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_target_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_action_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_user_id_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_occurred_at", table_name="audit_events")
    op.drop_index("ix_audit_events_event_id", table_name="audit_events")
    op.drop_table("audit_events")
