"""Memory event log persistence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.memory_event_log import MemoryEventLog


async def write_memory_event(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trace_id: str,
    event_type: str,
    memory_type: str,
    summary: str | None = None,
    memory_id: uuid.UUID | None = None,
    agent_run_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> MemoryEventLog:
    row = MemoryEventLog(
        tenant_id=tenant_id,
        user_id=user_id,
        trace_id=trace_id,
        event_type=event_type,
        memory_type=memory_type,
        summary=(summary or "")[:500] or None,
        memory_id=memory_id,
        agent_run_id=agent_run_id,
        metadata_=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row
