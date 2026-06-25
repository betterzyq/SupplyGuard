"""Memory HTTP routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.schemas.memory import (
    LongTermMemoryCreateRequest,
    LongTermMemoryCreateResponse,
    LongTermMemoryItem,
    LongTermMemoryListResponse,
    SessionMemoryResponse,
)
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.memory.long_term import create_memory, delete_memory, list_tenant_memories, list_user_memories
from packages.memory.memory_types import MemoryScope, MemoryWriteEvent
from packages.memory.short_term import clear_session, get_recent_messages

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("/session/{session_id}", response_model=SessionMemoryResponse)
async def get_session_memory(
    session_id: str,
    user_context: UserContext = Depends(get_user_context),
) -> SessionMemoryResponse:
    messages = await get_recent_messages(
        str(user_context.tenant_id),
        str(user_context.user_id),
        session_id,
    )
    return SessionMemoryResponse(
        session_id=session_id,
        messages=[message.to_dict() for message in messages],
    )


@router.post("/session/{session_id}/clear")
async def clear_session_memory(
    session_id: str,
    user_context: UserContext = Depends(get_user_context),
) -> dict[str, str]:
    await clear_session(
        str(user_context.tenant_id),
        str(user_context.user_id),
        session_id,
    )
    return {"status": "cleared", "session_id": session_id}


@router.get("/long-term", response_model=LongTermMemoryListResponse)
async def list_long_term_memory(
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> LongTermMemoryListResponse:
    if user_context.is_admin:
        records = await list_tenant_memories(session, user_context)
    else:
        records = await list_user_memories(session, user_context)
    items = [
        LongTermMemoryItem(
            id=str(record.id),
            memory_type=record.memory_type,
            content=record.content,
            summary=record.summary,
            supplier_id=str(record.supplier_id) if record.supplier_id else None,
            confidence=record.confidence,
            importance=record.importance,
            metadata=record.metadata_,
        )
        for record in records
    ]
    return LongTermMemoryListResponse(items=items)


@router.post("/long-term", response_model=LongTermMemoryCreateResponse)
async def create_long_term_memory(
    payload: LongTermMemoryCreateRequest,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> LongTermMemoryCreateResponse:
    supplier_uuid = uuid.UUID(payload.supplier_id) if payload.supplier_id else None
    event = MemoryWriteEvent(
        content=payload.content,
        memory_type=payload.memory_type,
        scope=MemoryScope.USER,
        supplier_id=supplier_uuid,
        importance=payload.importance,
        is_user_explicit=True,
    )
    row = await create_memory(session, user_context, event)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory content rejected by policy",
        )
    await session.commit()
    return LongTermMemoryCreateResponse(id=str(row.id), memory_type=row.memory_type, content=row.content)


@router.delete("/long-term/{memory_id}")
async def delete_long_term_memory(
    memory_id: uuid.UUID,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, str]:
    deleted = await delete_memory(session, user_context, memory_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found or forbidden")
    await session.commit()
    return {"status": "deleted", "id": str(memory_id)}
