"""Agent run repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.config import get_settings
from packages.common.llm.factory import get_llm_client
from packages.common.llm.usage import enrich_token_usage
from packages.common.db.models.agent_run import AgentRun


async def create_agent_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    trace_id: str,
    session_id: str,
    query: str,
    workflow_version: str = "mvp3-v1",
    status: str = "running",
    request_id: str | None = None,
) -> AgentRun:
    run = AgentRun(
        tenant_id=tenant_id,
        user_id=user_id,
        trace_id=trace_id,
        session_id=session_id,
        query=query,
        workflow_version=workflow_version,
        status=status,
        request_id=request_id,
    )
    session.add(run)
    await session.flush()
    return run


async def finalize_agent_run(
    session: AsyncSession,
    agent_run: AgentRun,
    *,
    status: str,
    final_answer: str | None,
    citations: list[dict[str, Any]],
    token_usage: dict[str, Any],
    latency_ms: int,
    nodes_executed: list[str],
    error_message: str | None = None,
    node_spans: list[dict[str, Any]] | None = None,
) -> AgentRun:
    settings = get_settings()
    provider = get_llm_client(settings)
    model_info = provider.get_model_info()
    enriched_usage = enrich_token_usage(token_usage, model=model_info.model)
    agent_run.status = status
    agent_run.final_answer = final_answer
    agent_run.citations = citations
    agent_run.token_usage = enriched_usage
    agent_run.latency_ms = latency_ms
    agent_run.nodes_executed = nodes_executed
    agent_run.error_message = error_message
    agent_run.llm_model = model_info.model
    agent_run.estimated_cost = float(enriched_usage.get("estimated_cost") or 0)
    await session.flush()
    return agent_run
