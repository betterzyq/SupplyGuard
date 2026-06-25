"""Graph retrieval log model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.db.base import Base, UUIDPrimaryKeyMixin


class GraphRetrievalLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "graph_retrieval_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True
    )
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    query_type: Mapped[str] = mapped_column(String(64), nullable=False)
    cypher_template: Mapped[str] = mapped_column(String(64), nullable=False)
    cypher_query: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parameters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    paths_found: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    permission_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
