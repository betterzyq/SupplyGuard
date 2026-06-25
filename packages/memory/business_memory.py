"""Business memory helpers."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.memory import Memory
from packages.memory.memory_types import BUSINESS_MEMORY_TYPES, MemoryScope, MemoryRecord


def memory_orm_to_record(row: Memory, *, scope: str | None = None) -> MemoryRecord:
    meta = row.metadata_ or {}
    return MemoryRecord(
        id=row.id,
        tenant_id=row.tenant_id,
        user_id=row.user_id,
        memory_type=row.memory_type,
        content=row.content,
        summary=row.summary,
        supplier_id=row.supplier_id,
        source_agent_run_id=row.source_agent_run_id,
        confidence=row.confidence,
        importance=row.importance,
        expires_at=row.expires_at,
        metadata_=meta,
        scope=scope or meta.get("scope", MemoryScope.BUSINESS),
    )


async def list_business_memories(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    supplier_id: uuid.UUID | None = None,
    limit: int = 20,
) -> list[MemoryRecord]:
    conditions = [
        Memory.tenant_id == tenant_id,
        Memory.memory_type.in_(tuple(BUSINESS_MEMORY_TYPES)),
    ]
    if supplier_id is not None:
        conditions.append(
            or_(
                Memory.supplier_id == supplier_id,
                Memory.metadata_.contains({"scope": MemoryScope.BUSINESS}),
            )
        )
    stmt = (
        select(Memory)
        .where(and_(*conditions))
        .order_by(Memory.importance.desc(), Memory.created_at.desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [memory_orm_to_record(row, scope=MemoryScope.BUSINESS) for row in rows]
