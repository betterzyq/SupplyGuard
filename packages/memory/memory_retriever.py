"""Memory retrieval for agent workflow."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.common.db.models.supplier import Supplier
from packages.memory.business_memory import list_business_memories
from packages.memory.long_term import list_user_memories
from packages.memory.memory_policy import is_memory_followup_query
from packages.memory.memory_types import MemoryScope
from packages.memory.short_term import get_recent_entities, get_recent_messages


async def resolve_supplier_id_from_code(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_code: str | None,
) -> uuid.UUID | None:
    if not supplier_code:
        return None
    result = await session.execute(
        select(Supplier.id).where(
            Supplier.tenant_id == tenant_id,
            Supplier.code == supplier_code.upper(),
        )
    )
    return result.scalar_one_or_none()


async def retrieve_memory_evidence(
    session: AsyncSession,
    user_context: UserContext,
    query: str,
    *,
    session_id: str,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    tenant_id = str(user_context.tenant_id)
    user_id = str(user_context.user_id)

    session_messages = await get_recent_messages(tenant_id, user_id, session_id, limit=limit)
    recent_entities = await get_recent_entities(tenant_id, user_id, session_id)

    supplier_code = recent_entities.get("supplier")
    if not supplier_code:
        match = re.search(r"\b(SUP-\d{3})\b", query, re.IGNORECASE)
        if match:
            supplier_code = match.group(1).upper()

    supplier_uuid = await resolve_supplier_id_from_code(session, user_context.tenant_id, supplier_code)
    if user_context.is_external_supplier and user_context.supplier_id:
        supplier_uuid = user_context.supplier_id

    user_memories = await list_user_memories(session, user_context, limit=limit)
    business_memories = await list_business_memories(
        session,
        tenant_id=user_context.tenant_id,
        supplier_id=supplier_uuid,
        limit=limit,
    )

    evidence: list[dict[str, Any]] = []

    for message in session_messages[-3:]:
        evidence.append(
            {
                "evidence_id": f"session:{message.timestamp}",
                "evidence_type": "memory",
                "source_id": session_id,
                "source_title": f"Session {message.role}",
                "content": message.content[:400],
                "score": 0.45,
                "confidence": 0.6,
                "permission_scope": "session",
                "citation": None,
                "metadata": {"role": message.role, "entities": message.entities, "ephemeral": True},
            }
        )

    for record in business_memories:
        score = record.importance * record.confidence
        if supplier_code and supplier_code.upper() in record.content.upper():
            score += 0.2
        if is_memory_followup_query(query):
            score += 0.15
        evidence.append(
            {
                "evidence_id": str(record.id),
                "evidence_type": "memory",
                "source_id": str(record.id),
                "source_title": record.memory_type,
                "content": record.summary or record.content,
                "score": min(score, 1.0),
                "confidence": record.confidence,
                "permission_scope": MemoryScope.BUSINESS,
                "citation": f"[memory:{record.id}]",
                "metadata": {"memory_type": record.memory_type, "scope": MemoryScope.BUSINESS},
            }
        )

    for record in user_memories[:5]:
        evidence.append(
            {
                "evidence_id": str(record.id),
                "evidence_type": "memory",
                "source_id": str(record.id),
                "source_title": record.memory_type,
                "content": record.summary or record.content,
                "score": record.importance * 0.8,
                "confidence": record.confidence,
                "permission_scope": MemoryScope.USER,
                "citation": f"[memory:{record.id}]",
                "metadata": {"memory_type": record.memory_type, "scope": MemoryScope.USER},
            }
        )

    evidence.sort(key=lambda item: item.get("score", 0), reverse=True)
    return evidence[:limit], recent_entities
