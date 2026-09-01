"""add ingestion schema

Revision ID: 3baf1c2d7e90
Revises: 88a1df0e92a3
Create Date: 2026-08-31 03:40:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "3baf1c2d7e90"
down_revision: Union[str, None] = "88a1df0e92a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("checkpoint_before", sa.JSON(), nullable=True),
        sa.Column("checkpoint_after", sa.JSON(), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False),
        sa.Column("normalized_count", sa.Integer(), nullable=False),
        sa.Column("persisted_count", sa.Integer(), nullable=False),
        sa.Column("duplicate_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_runs")),
    )
    op.create_index("ix_ingestion_runs_provider", "ingestion_runs", ["provider"], unique=False)
    op.create_index(
        "ix_ingestion_runs_source_name", "ingestion_runs", ["source_name"], unique=False
    )
    op.create_index("ix_ingestion_runs_started_at", "ingestion_runs", ["started_at"], unique=False)
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"], unique=False)

    op.create_table(
        "ingestion_checkpoints",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["last_run_id"],
            ["ingestion_runs.id"],
            name=op.f("fk_ingestion_checkpoints_last_run_id_ingestion_runs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ingestion_checkpoints")),
        sa.UniqueConstraint(
            "provider",
            "source_name",
            name="uq_ingestion_checkpoints_provider_source",
        ),
    )
    op.create_index(
        "ix_ingestion_checkpoints_provider",
        "ingestion_checkpoints",
        ["provider"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_checkpoints_source_name",
        "ingestion_checkpoints",
        ["source_name"],
        unique=False,
    )
    op.create_index(
        "ix_ingestion_checkpoints_updated_at",
        "ingestion_checkpoints",
        ["updated_at"],
        unique=False,
    )

    op.add_column("events", sa.Column("dedup_key", sa.String(length=500), nullable=True))
    op.add_column("events", sa.Column("ingestion_run_id", sa.Integer(), nullable=True))
    op.add_column("events", sa.Column("source_provider", sa.String(length=100), nullable=True))
    op.add_column("events", sa.Column("source_instance", sa.String(length=255), nullable=True))
    op.add_column("events", sa.Column("source_index", sa.String(length=255), nullable=True))
    op.add_column("events", sa.Column("source_record_id", sa.String(length=500), nullable=True))
    op.add_column(
        "events", sa.Column("normalization_version", sa.String(length=50), nullable=True)
    )
    op.add_column("events", sa.Column("normalization_warnings", sa.JSON(), nullable=True))
    op.add_column("events", sa.Column("raw_payload", sa.JSON(), nullable=True))
    op.create_foreign_key(
        op.f("fk_events_ingestion_run_id_ingestion_runs"),
        "events",
        "ingestion_runs",
        ["ingestion_run_id"],
        ["id"],
    )
    op.create_index("ix_events_dedup_key", "events", ["dedup_key"], unique=True)
    op.create_index(
        "ix_events_ingestion_run_id", "events", ["ingestion_run_id"], unique=False
    )
    op.create_index(
        "ix_events_source_instance", "events", ["source_instance"], unique=False
    )
    op.create_index("ix_events_source_provider", "events", ["source_provider"], unique=False)
    op.create_index(
        "ix_events_source_record_id", "events", ["source_record_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_events_source_record_id", table_name="events")
    op.drop_index("ix_events_source_provider", table_name="events")
    op.drop_index("ix_events_source_instance", table_name="events")
    op.drop_index("ix_events_ingestion_run_id", table_name="events")
    op.drop_index("ix_events_dedup_key", table_name="events")
    op.drop_constraint(
        op.f("fk_events_ingestion_run_id_ingestion_runs"), "events", type_="foreignkey"
    )
    op.drop_column("events", "raw_payload")
    op.drop_column("events", "normalization_warnings")
    op.drop_column("events", "normalization_version")
    op.drop_column("events", "source_record_id")
    op.drop_column("events", "source_index")
    op.drop_column("events", "source_instance")
    op.drop_column("events", "source_provider")
    op.drop_column("events", "ingestion_run_id")
    op.drop_column("events", "dedup_key")

    op.drop_index("ix_ingestion_checkpoints_updated_at", table_name="ingestion_checkpoints")
    op.drop_index("ix_ingestion_checkpoints_source_name", table_name="ingestion_checkpoints")
    op.drop_index("ix_ingestion_checkpoints_provider", table_name="ingestion_checkpoints")
    op.drop_table("ingestion_checkpoints")

    op.drop_index("ix_ingestion_runs_status", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_started_at", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_source_name", table_name="ingestion_runs")
    op.drop_index("ix_ingestion_runs_provider", table_name="ingestion_runs")
    op.drop_table("ingestion_runs")
