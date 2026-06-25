"""Tool call log (Stage C placeholder, used by trace API in Stage B)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.common.db.base import Base, UUIDPrimaryKeyMixin


class ToolCallLog(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "tool_call_logs"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trace_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    agent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_input: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    tool_output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    permission_decision: Mapped[str] = mapped_column(String(32), nullable=False, default="allowed")
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
