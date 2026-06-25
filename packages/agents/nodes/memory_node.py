"""Recall short-term and long-term memory."""

from __future__ import annotations

import uuid

from packages.agents.state import AgentState
from packages.memory.memory_retriever import retrieve_memory_evidence
from packages.observability.repositories.memory_event_repo import write_memory_event


async def memory_node(state: AgentState) -> AgentState:
    if not state.get("use_memory", True):
        return {"nodes_executed": ["memory_skipped"]}

    if state.get("permission_decision") and not state["permission_decision"].allowed:
        return {"nodes_executed": ["memory_skipped"]}

    user_context = state["user_context"]
    session = state["db_session"]
    query = state["query"]
    session_id = state.get("session_id") or state["trace_id"]

    memory_evidence, recent_entities = await retrieve_memory_evidence(
        session,
        user_context,
        query,
        session_id=session_id,
        limit=state.get("top_k", 10),
    )

    agent_run_id = state.get("agent_run_id")
    for item in memory_evidence:
        await write_memory_event(
            session,
            tenant_id=user_context.tenant_id,
            user_id=user_context.user_id,
            trace_id=state["trace_id"],
            event_type="read",
            memory_type=str(item.get("metadata", {}).get("scope") or item.get("evidence_type") or "session"),
            summary=str(item.get("content", ""))[:200],
            agent_run_id=uuid.UUID(agent_run_id) if agent_run_id else None,
            metadata={"source_id": item.get("source_id"), "citation": item.get("citation")},
        )

    return {
        "memory_evidence": memory_evidence,
        "recent_entities": recent_entities,
        "nodes_executed": ["memory"],
    }
