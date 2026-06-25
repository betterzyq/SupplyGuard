"""Retrieval log model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.db.base import Base, UUIDPrimaryKeyMixin


class RetrievalLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "retrieval_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    retriever_type: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filter_applied: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_size_config: Mapped[int] = mapped_column(Integer, nullable=False)
    results: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    reranker_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
