"""Long-term memory persistence."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.common.db.models.memory import Memory
from packages.memory.business_memory import memory_orm_to_record
from packages.memory.memory_policy import can_read_memory, sanitize_memory_content, should_write_memory
from packages.memory.memory_types import MemoryRecord, MemoryScope, MemoryWriteEvent


async def create_memory(
    session: AsyncSession,
    user_context: UserContext,
    event: MemoryWriteEvent,
) -> Memory | None:
    allowed, reason = should_write_memory(event)
    if not allowed:
        return None

    content = sanitize_memory_content(event.content)
    summary = content[:160] if len(content) > 160 else content
    metadata = dict(event.metadata)
    metadata["scope"] = event.scope
    metadata["write_reason"] = reason

    row = Memory(
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        memory_type=event.memory_type or "feedback",
        content=content,
        summary=summary,
        supplier_id=event.supplier_id,
        source_agent_run_id=event.source_agent_run_id,
        confidence=event.confidence,
        importance=event.importance,
        expires_at=event.metadata.get("expires_at"),
        metadata_=metadata,
    )
    session.add(row)
    await session.flush()
    return row


async def list_user_memories(
    session: AsyncSession,
    user_context: UserContext,
    *,
    limit: int = 50,
) -> list[MemoryRecord]:
    stmt = (
        select(Memory)
        .where(
            Memory.tenant_id == user_context.tenant_id,
            Memory.user_id == user_context.user_id,
        )
        .order_by(Memory.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    records = [memory_orm_to_record(row) for row in rows]
    return [item for item in records if can_read_memory(user_context, item)]


async def list_tenant_memories(
    session: AsyncSession,
    user_context: UserContext,
    *,
    limit: int = 100,
) -> list[MemoryRecord]:
    stmt = (
        select(Memory)
        .where(Memory.tenant_id == user_context.tenant_id)
        .order_by(Memory.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    records = [memory_orm_to_record(row) for row in rows]
    return [item for item in records if can_read_memory(user_context, item)]


async def get_memory_by_id(
    session: AsyncSession,
    memory_id: uuid.UUID,
) -> Memory | None:
    return (await session.execute(select(Memory).where(Memory.id == memory_id))).scalar_one_or_none()


async def delete_memory(
    session: AsyncSession,
    user_context: UserContext,
    memory_id: uuid.UUID,
) -> bool:
    row = await get_memory_by_id(session, memory_id)
    if row is None:
        return False
    record = memory_orm_to_record(row)
    if not can_read_memory(user_context, record):
        return False
    if not user_context.is_admin and row.user_id != user_context.user_id:
        return False
    await session.execute(delete(Memory).where(Memory.id == memory_id))
    return True
