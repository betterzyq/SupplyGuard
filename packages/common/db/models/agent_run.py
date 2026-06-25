"""Agent run model."""

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "agent_runs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trace_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    nodes_executed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    llm_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
