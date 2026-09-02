"""add versioned detection execution provenance

Revision ID: 6c4d2e8f1a90
Revises: 3baf1c2d7e90
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6c4d2e8f1a90"
down_revision: Union[str, None] = "3baf1c2d7e90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for name, column in (
        ("structured_logic", sa.Column("structured_logic", sa.JSON(), nullable=True)),
        ("rule_type", sa.Column("rule_type", sa.String(length=20), nullable=True)),
        ("version", sa.Column("version", sa.Integer(), nullable=True)),
        ("lookback_window_seconds", sa.Column("lookback_window_seconds", sa.Integer(), nullable=True)),
        ("schedule_interval_seconds", sa.Column("schedule_interval_seconds", sa.Integer(), nullable=True)),
        ("max_events_scanned", sa.Column("max_events_scanned", sa.Integer(), nullable=True)),
        ("suppression_window_seconds", sa.Column("suppression_window_seconds", sa.Integer(), nullable=True)),
        ("enabled_for_execution", sa.Column("enabled_for_execution", sa.Boolean(), nullable=True)),
    ):
        op.add_column("detection_rules", column)

    op.execute(
        sa.text(
            "UPDATE detection_rules SET rule_type='single', version=1, "
            "lookback_window_seconds=3600, max_events_scanned=10000, "
            "suppression_window_seconds=0, enabled_for_execution=FALSE "
            "WHERE rule_type IS NULL"
        )
    )
    for name in (
        "rule_type", "version", "lookback_window_seconds", "max_events_scanned",
        "suppression_window_seconds", "enabled_for_execution",
    ):
        op.alter_column("detection_rules", name, nullable=False)
    op.create_index("ix_detection_rules_rule_type", "detection_rules", ["rule_type"])
    op.create_index("ix_detection_rules_enabled_for_execution", "detection_rules", ["enabled_for_execution"])

    op.create_table(
        "detection_rule_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("detection_rule_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rule_type", sa.String(length=20), nullable=False),
        sa.Column("structured_logic", sa.JSON(), nullable=True),
        sa.Column("legacy_query", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["detection_rule_id"], ["detection_rules.id"], name=op.f("fk_detection_rule_versions_detection_rule_id_detection_rules")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_detection_rule_versions")),
        sa.UniqueConstraint("detection_rule_id", "version", name="uq_detection_rule_versions_rule_version"),
    )
    op.create_index("ix_detection_rule_versions_rule_id", "detection_rule_versions", ["detection_rule_id"])
    op.execute(
        sa.text(
            "INSERT INTO detection_rule_versions "
            "(detection_rule_id, version, rule_type, structured_logic, legacy_query, created_at) "
            "SELECT id, version, rule_type, structured_logic, query, created_at FROM detection_rules"
        )
    )

    op.create_table(
        "detection_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("detection_rule_id", sa.Integer(), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("events_scanned", sa.Integer(), nullable=False),
        sa.Column("alerts_created", sa.Integer(), nullable=False),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["detection_rule_id"], ["detection_rules.id"], name=op.f("fk_detection_runs_detection_rule_id_detection_rules")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_detection_runs")),
    )
    op.create_index("ix_detection_runs_rule_id", "detection_runs", ["detection_rule_id"])
    op.create_index("ix_detection_runs_started_at", "detection_runs", ["started_at"])
    op.create_index("ix_detection_runs_status", "detection_runs", ["status"])

    for column in (
        sa.Column("detection_rule_id", sa.Integer(), nullable=True),
        sa.Column("rule_version", sa.Integer(), nullable=True),
        sa.Column("detection_run_id", sa.Integer(), nullable=True),
        sa.Column("fingerprint", sa.String(length=255), nullable=True),
        sa.Column("rule_logic_snapshot", sa.JSON(), nullable=True),
        sa.Column("match_explanation", sa.JSON(), nullable=True),
    ):
        op.add_column("alerts", column)
    op.create_foreign_key("fk_alerts_detection_rule_id_detection_rules", "alerts", "detection_rules", ["detection_rule_id"], ["id"])
    op.create_foreign_key("fk_alerts_detection_run_id_detection_runs", "alerts", "detection_runs", ["detection_run_id"], ["id"])
    op.create_index("ix_alerts_detection_rule_id", "alerts", ["detection_rule_id"])
    op.create_index("ix_alerts_detection_run_id", "alerts", ["detection_run_id"])
    op.create_index("ix_alerts_fingerprint", "alerts", ["fingerprint"], unique=True)
    op.add_column("alert_event", sa.Column("stage", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("alert_event", "stage")
    op.drop_index("ix_alerts_fingerprint", table_name="alerts")
    op.drop_index("ix_alerts_detection_run_id", table_name="alerts")
    op.drop_index("ix_alerts_detection_rule_id", table_name="alerts")
    op.drop_constraint("fk_alerts_detection_run_id_detection_runs", "alerts", type_="foreignkey")
    op.drop_constraint("fk_alerts_detection_rule_id_detection_rules", "alerts", type_="foreignkey")
    for name in ("match_explanation", "rule_logic_snapshot", "fingerprint", "detection_run_id", "rule_version", "detection_rule_id"):
        op.drop_column("alerts", name)
    op.drop_index("ix_detection_runs_status", table_name="detection_runs")
    op.drop_index("ix_detection_runs_started_at", table_name="detection_runs")
    op.drop_index("ix_detection_runs_rule_id", table_name="detection_runs")
    op.drop_table("detection_runs")
    op.drop_index("ix_detection_rule_versions_rule_id", table_name="detection_rule_versions")
    op.drop_table("detection_rule_versions")
    op.drop_index("ix_detection_rules_enabled_for_execution", table_name="detection_rules")
    op.drop_index("ix_detection_rules_rule_type", table_name="detection_rules")
    for name in (
        "enabled_for_execution", "suppression_window_seconds", "max_events_scanned",
        "schedule_interval_seconds", "lookback_window_seconds", "version", "rule_type",
        "structured_logic",
    ):
        op.drop_column("detection_rules", name)
