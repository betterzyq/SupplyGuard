"""add trace_id to benchmark_runs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("benchmark_runs", sa.Column("trace_id", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_benchmark_runs_trace_id"), "benchmark_runs", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_benchmark_runs_trace_id"), table_name="benchmark_runs")
    op.drop_column("benchmark_runs", "trace_id")
