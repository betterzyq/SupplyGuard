"""Node span persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.agent_node_span import AgentNodeSpan


async def write_node_span(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trace_id: str,
    node_name: str,
    start_time: datetime,
    end_time: datetime | None = None,
    latency_ms: int | None = None,
    status: str = "completed",
    error_message: str | None = None,
    agent_run_id: uuid.UUID | None = None,
) -> AgentNodeSpan:
    span = AgentNodeSpan(
        tenant_id=tenant_id,
        user_id=user_id,
        trace_id=trace_id,
        node_name=node_name,
        start_time=start_time,
        end_time=end_time or datetime.now(UTC),
        latency_ms=latency_ms,
        status=status,
        error_message=error_message,
        agent_run_id=agent_run_id,
    )
    session.add(span)
    await session.flush()
    return span


def span_to_dict(span: AgentNodeSpan) -> dict[str, Any]:
    return {
        "id": str(span.id),
        "node_name": span.node_name,
        "start_time": span.start_time.isoformat() if span.start_time else None,
        "end_time": span.end_time.isoformat() if span.end_time else None,
        "latency_ms": span.latency_ms,
        "status": span.status,
        "error_message": span.error_message,
    }
