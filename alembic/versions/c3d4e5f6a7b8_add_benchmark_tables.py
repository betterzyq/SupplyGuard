"""add benchmark tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "benchmark_runs",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("mode", sa.String(length=64), nullable=False),
        sa.Column("dataset_name", sa.String(length=128), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmark_runs_tenant_id"), "benchmark_runs", ["tenant_id"], unique=False)

    op.create_table(
        "benchmark_results",
        sa.Column("benchmark_run_id", sa.UUID(), nullable=False),
        sa.Column("question_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(length=64), nullable=False),
        sa.Column("ground_truth", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("predicted_answer", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("retrieved_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("graph_paths", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("memory_used", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["benchmark_run_id"], ["benchmark_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmark_results_benchmark_run_id"), "benchmark_results", ["benchmark_run_id"], unique=False)
    op.create_index(op.f("ix_benchmark_results_question_id"), "benchmark_results", ["question_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_results_question_id"), table_name="benchmark_results")
    op.drop_index(op.f("ix_benchmark_results_benchmark_run_id"), table_name="benchmark_results")
    op.drop_table("benchmark_results")
    op.drop_index(op.f("ix_benchmark_runs_tenant_id"), table_name="benchmark_runs")
    op.drop_table("benchmark_runs")
