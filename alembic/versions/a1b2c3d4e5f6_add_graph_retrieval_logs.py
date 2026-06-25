"""add graph_retrieval_logs

Revision ID: a1b2c3d4e5f6
Revises: 9b2e15f09ec9
Create Date: 2026-06-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9b2e15f09ec9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "graph_retrieval_logs",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(length=64), nullable=False),
        sa.Column("cypher_template", sa.String(length=64), nullable=False),
        sa.Column("cypher_query", sa.Text(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("paths_found", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("permission_decision", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_graph_retrieval_logs_tenant_id"), "graph_retrieval_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_graph_retrieval_logs_trace_id"), "graph_retrieval_logs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_graph_retrieval_logs_trace_id"), table_name="graph_retrieval_logs")
    op.drop_index(op.f("ix_graph_retrieval_logs_tenant_id"), table_name="graph_retrieval_logs")
    op.drop_table("graph_retrieval_logs")
