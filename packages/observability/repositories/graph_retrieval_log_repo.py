"""Graph retrieval log repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.graph_retrieval_log import GraphRetrievalLog


async def write_graph_retrieval_log(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trace_id: str,
    query: str,
    query_type: str,
    cypher_template: str,
    cypher_query: str,
    parameters: dict[str, Any],
    paths_found: list[dict[str, Any]],
    result_count: int,
    latency_ms: int,
    permission_decision: str,
    agent_run_id: uuid.UUID | None = None,
    error_message: str | None = None,
) -> GraphRetrievalLog:
    entry = GraphRetrievalLog(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_run_id=agent_run_id,
        trace_id=trace_id,
        query=query,
        query_type=query_type,
        cypher_template=cypher_template,
        cypher_query=cypher_query,
        parameters=parameters,
        paths_found=paths_found,
        result_count=result_count,
        latency_ms=latency_ms,
        permission_decision=permission_decision,
        error_message=error_message,
    )
    session.add(entry)
    await session.flush()
    return entry
