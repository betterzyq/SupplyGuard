"""Add only P5 workspace tables; never alter legacy business data.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""

from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None
# Immutable revision-local copies protect the migration from later ORM changes.
# Column definitions live in this revision's checked-in companion SQL snapshot.


def upgrade():
    from pathlib import Path

    for statement in (
        (Path(__file__).parent / "phase5_schema.sql").read_text().split(";")
    ):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for name in [
        "sg5_subscriptions",
        "sg5_events",
        "sg5_reports",
        "sg5_idempotency",
        "sg5_activity",
        "sg5_tasks",
        "sg5_links",
        "sg5_records",
        "sg5_import_batches",
    ]:
        op.drop_table(name)
