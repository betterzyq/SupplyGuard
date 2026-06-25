"""Retrieval log repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.retrieval_log import RetrievalLog


async def write_retrieval_log(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trace_id: str,
    query: str,
    filter_applied: dict[str, Any],
    top_k: int,
    chunk_size_config: int,
    results: list[dict[str, Any]],
    latency_ms: int,
    result_count: int,
    agent_run_id: uuid.UUID | None = None,
    retriever_type: str = "secure_vector",
    reranker_used: bool = False,
) -> RetrievalLog:
    entry = RetrievalLog(
        tenant_id=tenant_id,
        agent_run_id=agent_run_id,
        trace_id=trace_id,
        user_id=user_id,
        retriever_type=retriever_type,
        query=query,
        filter_applied=filter_applied,
        top_k=top_k,
        chunk_size_config=chunk_size_config,
        results=results,
        reranker_used=reranker_used,
        latency_ms=latency_ms,
        result_count=result_count,
    )
    session.add(entry)
    await session.flush()
    return entry
