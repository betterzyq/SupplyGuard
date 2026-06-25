"""Alembic migration — memories table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("memory_type", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("supplier_id", sa.UUID(), nullable=True),
        sa.Column("source_agent_run_id", sa.UUID(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("importance", sa.Float(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["source_agent_run_id"], ["agent_runs.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_memories_memory_type"), "memories", ["memory_type"], unique=False)
    op.create_index(op.f("ix_memories_supplier_id"), "memories", ["supplier_id"], unique=False)
    op.create_index(op.f("ix_memories_tenant_id"), "memories", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_memories_user_id"), "memories", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_memories_user_id"), table_name="memories")
    op.drop_index(op.f("ix_memories_tenant_id"), table_name="memories")
    op.drop_index(op.f("ix_memories_supplier_id"), table_name="memories")
    op.drop_index(op.f("ix_memories_memory_type"), table_name="memories")
    op.drop_table("memories")
