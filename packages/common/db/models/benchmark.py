"""Benchmark run and result ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.db.base import Base, UUIDPrimaryKeyMixin


class BenchmarkRun(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "benchmark_runs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mode: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_name: Mapped[str] = mapped_column(String(128), nullable=False, default="supplyguard_eval")
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class BenchmarkResult(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "benchmark_results"

    benchmark_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("benchmark_runs.id"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(String(64), nullable=False, default="general")
    ground_truth: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    predicted_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    retrieved_ids: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    graph_paths: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    memory_used: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
