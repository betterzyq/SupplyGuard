"""P5 additive tenant workspace. Legacy business tables remain unchanged."""

import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Scoped:
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )


class ImportBatch(Base, Scoped, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sg5_import_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fingerprint"),
        UniqueConstraint("tenant_id", "id"),
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rows: Mapped[list] = mapped_column(JSONB, nullable=False)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkspaceRecord(Base, Scoped, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sg5_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kind", "code"),
        UniqueConstraint("tenant_id", "id"),
        CheckConstraint(
            "kind in ('site','order','shipment','event','prediction','simulation')"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "import_batch_id"],
            ["sg5_import_batches.tenant_id", "sg5_import_batches.id"],
        ),
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)


class RecordLink(Base, Scoped, UUIDPrimaryKeyMixin):
    __tablename__ = "sg5_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_id", "target_id", "relation"),
        ForeignKeyConstraint(
            ["tenant_id", "source_id"], ["sg5_records.tenant_id", "sg5_records.id"]
        ),
        ForeignKeyConstraint(
            ["tenant_id", "target_id"], ["sg5_records.tenant_id", "sg5_records.id"]
        ),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relation: Mapped[str] = mapped_column(String(32), nullable=False)


class ActionTask(Base, Scoped, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "sg5_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "record_id"], ["sg5_records.tenant_id", "sg5_records.id"]
        ),
        CheckConstraint(
            "state in ('open','in_progress','pending_verification','completed','cancelled')"
        ),
        CheckConstraint("version >= 1"),
    )
    record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="open", index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measures: Mapped[str] = mapped_column(Text, nullable=False, default="")
    actual_cost_cny: Mapped[str] = mapped_column(
        String(32), nullable=False, default="0.00"
    )
    result: Mapped[str] = mapped_column(Text, nullable=False, default="")


class WorkspaceActivity(Base, Scoped, UUIDPrimaryKeyMixin):
    __tablename__ = "sg5_activity"
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyRecord(Base, Scoped, UUIDPrimaryKeyMixin):
    __tablename__ = "sg5_idempotency"
    __table_args__ = (UniqueConstraint("tenant_id", "operation", "key"),)
    operation: Mapped[str] = mapped_column(String(80), nullable=False)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkspaceReport(Base, Scoped, UUIDPrimaryKeyMixin):
    __tablename__ = "sg5_reports"
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class LocalEvent(Base, Scoped):
    __tablename__ = "sg5_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    topic: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LocalSubscription(Base, Scoped, UUIDPrimaryKeyMixin):
    __tablename__ = "sg5_subscriptions"
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    topics: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
