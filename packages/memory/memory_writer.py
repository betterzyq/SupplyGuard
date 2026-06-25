"""Memory write helpers for workflow completion."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.memory.long_term import create_memory
from packages.memory.memory_policy import classify_memory_type, detect_sensitive_content
from packages.memory.memory_types import (
    BusinessMemoryType,
    MemoryScope,
    MemoryWriteEvent,
    SessionMessage,
)
from packages.memory.short_term import append_message, now_iso


def extract_entities(text: str) -> dict[str, str]:
    entities: dict[str, str] = {}
    supplier = re.search(r"\b(SUP-\d{3})\b", text, re.IGNORECASE)
    if supplier:
        entities["supplier"] = supplier.group(1).upper()
    product = re.search(r"\b(P\d{3})\b", text, re.IGNORECASE)
    if product:
        entities["product"] = product.group(1).upper()
    return entities


def build_analysis_memory_event(
    query: str,
    answer: str,
    *,
    supplier_id: uuid.UUID | None,
    agent_run_id: uuid.UUID | None,
    entities: dict[str, str],
) -> MemoryWriteEvent | None:
    combined = f"{query}\n{answer}"
    if not any(k in combined for k in ("风险", "risk", "SUP-", "供应商")):
        return None
    if detect_sensitive_content(combined):
        return None

    summary = answer[:400]
    return MemoryWriteEvent(
        content=f"分析结论：{summary}",
        memory_type=BusinessMemoryType.SUPPLIER_RISK_HISTORY,
        scope=MemoryScope.BUSINESS,
        supplier_id=supplier_id,
        source_agent_run_id=agent_run_id,
        confidence=0.85,
        importance=0.7,
        metadata={"entities": entities},
        is_analysis_conclusion=True,
    )


async def write_session_turn(
    user_context: UserContext,
    session_id: str,
    *,
    query: str,
    answer: str,
    evidence_refs: list[str],
) -> None:
    entities = extract_entities(f"{query} {answer}")
    await append_message(
        str(user_context.tenant_id),
        str(user_context.user_id),
        session_id,
        SessionMessage(role="user", content=query, timestamp=now_iso(), entities=entities),
    )
    await append_message(
        str(user_context.tenant_id),
        str(user_context.user_id),
        session_id,
        SessionMessage(
            role="assistant",
            content=answer[:800],
            timestamp=now_iso(),
            entities=entities,
            evidence_refs=evidence_refs,
        ),
    )


async def write_long_term_from_turn(
    session: AsyncSession,
    user_context: UserContext,
    *,
    query: str,
    answer: str,
    supplier_id: uuid.UUID | None,
    agent_run_id: uuid.UUID | None,
    entities: dict[str, str],
    memory_written: list[dict[str, Any]],
) -> None:
    if any(k in query for k in ("偏好", "prefer", "以后请", "报告格式")):
        event = MemoryWriteEvent(
            content=query,
            memory_type=classify_memory_type(query),
            scope=MemoryScope.USER,
            is_user_explicit=True,
            importance=0.6,
        )
        row = await create_memory(session, user_context, event)
        if row:
            memory_written.append({"id": str(row.id), "memory_type": row.memory_type})

    analysis_event = build_analysis_memory_event(
        query,
        answer,
        supplier_id=supplier_id,
        agent_run_id=agent_run_id,
        entities=entities,
    )
    if analysis_event:
        row = await create_memory(session, user_context, analysis_event)
        if row:
            memory_written.append({"id": str(row.id), "memory_type": row.memory_type})
