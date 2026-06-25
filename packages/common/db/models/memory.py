"""Long-term memory PostgreSQL model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Memory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "memories"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    memory_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True, index=True
    )
    source_agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)
    importance: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    # Qdrant memory collection point id — reserved for semantic recall
    embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
