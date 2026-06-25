"""add observability tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("request_id", sa.String(length=128), nullable=True))
    op.add_column("agent_runs", sa.Column("llm_model", sa.String(length=128), nullable=True))
    op.add_column("agent_runs", sa.Column("estimated_cost", sa.Float(), nullable=True))
    op.create_index(op.f("ix_agent_runs_request_id"), "agent_runs", ["request_id"], unique=False)

    op.add_column("benchmark_results", sa.Column("trace_id", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_benchmark_results_trace_id"), "benchmark_results", ["trace_id"], unique=False)

    op.create_table(
        "agent_node_spans",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("node_name", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_node_spans_trace_id"), "agent_node_spans", ["trace_id"], unique=False)
    op.create_index(op.f("ix_agent_node_spans_agent_run_id"), "agent_node_spans", ["agent_run_id"], unique=False)

    op.create_table(
        "memory_event_logs",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("memory_id", sa.UUID(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memory_event_logs_trace_id"), "memory_event_logs", ["trace_id"], unique=False)

    op.create_table(
        "tool_call_logs",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("tool_input", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("permission_decision", sa.String(length=32), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_call_logs_trace_id"), "tool_call_logs", ["trace_id"], unique=False)

    op.create_table(
        "trace_requests",
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_trace_requests_request_id"), "trace_requests", ["request_id"], unique=False)
    op.create_index(op.f("ix_trace_requests_trace_id"), "trace_requests", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trace_requests_trace_id"), table_name="trace_requests")
    op.drop_index(op.f("ix_trace_requests_request_id"), table_name="trace_requests")
    op.drop_table("trace_requests")
    op.drop_index(op.f("ix_tool_call_logs_trace_id"), table_name="tool_call_logs")
    op.drop_table("tool_call_logs")
    op.drop_index(op.f("ix_memory_event_logs_trace_id"), table_name="memory_event_logs")
    op.drop_table("memory_event_logs")
    op.drop_index(op.f("ix_agent_node_spans_agent_run_id"), table_name="agent_node_spans")
    op.drop_index(op.f("ix_agent_node_spans_trace_id"), table_name="agent_node_spans")
    op.drop_table("agent_node_spans")
    op.drop_index(op.f("ix_benchmark_results_trace_id"), table_name="benchmark_results")
    op.drop_column("benchmark_results", "trace_id")
    op.drop_index(op.f("ix_agent_runs_request_id"), table_name="agent_runs")
    op.drop_column("agent_runs", "estimated_cost")
    op.drop_column("agent_runs", "llm_model")
    op.drop_column("agent_runs", "request_id")
