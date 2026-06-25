"""Persist session and long-term memory after successful turns."""

from __future__ import annotations

import uuid

from packages.agents.citation_manager import extract_all_citations
from packages.agents.state import AgentState
from packages.memory.memory_retriever import resolve_supplier_id_from_code
from packages.memory.memory_writer import extract_entities, write_long_term_from_turn, write_session_turn
from packages.observability.repositories.memory_event_repo import write_memory_event


async def memory_writer_node(state: AgentState) -> AgentState:
    if state.get("status") in {"blocked", "no_evidence"}:
        return {"nodes_executed": ["memory_writer_skipped"]}

    if not state.get("use_memory", True):
        return {"nodes_executed": ["memory_writer_skipped"]}

    user_context = state["user_context"]
    session = state["db_session"]
    session_id = state.get("session_id") or state["trace_id"]
    query = state["query"]
    answer = state.get("final_answer") or state.get("draft_answer") or ""

    citations = extract_all_citations(answer)
    evidence_refs = [
        f"doc:{doc_id}#{chunk}" for doc_id, chunk in citations["doc"]
    ] + [f"graph:{qt}#{pi}" for qt, pi in citations["graph"]] + [
        f"memory:{mid}" for mid in citations["memory"]
    ]

    await write_session_turn(
        user_context,
        session_id,
        query=query,
        answer=answer,
        evidence_refs=evidence_refs,
    )

    entities = state.get("recent_entities") or extract_entities(f"{query} {answer}")
    supplier_code = entities.get("supplier")
    supplier_id = await resolve_supplier_id_from_code(
        session, user_context.tenant_id, supplier_code
    )
    if user_context.is_external_supplier and user_context.supplier_id:
        supplier_id = user_context.supplier_id

    agent_run_id = state.get("agent_run_id")
    agent_run_uuid = uuid.UUID(agent_run_id) if agent_run_id else None

    memory_written: list[dict] = list(state.get("memory_written") or [])
    await write_long_term_from_turn(
        session,
        user_context,
        query=query,
        answer=answer,
        supplier_id=supplier_id,
        agent_run_id=agent_run_uuid,
        entities=entities,
        memory_written=memory_written,
    )

    await write_memory_event(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=state["trace_id"],
        event_type="write",
        memory_type="session",
        summary=query[:200],
        agent_run_id=agent_run_uuid,
        metadata={"memory_written_count": len(memory_written)},
    )
    for item in memory_written:
        await write_memory_event(
            session,
            tenant_id=user_context.tenant_id,
            user_id=user_context.user_id,
            trace_id=state["trace_id"],
            event_type="write",
            memory_type=str(item.get("memory_type") or "long_term"),
            summary=str(item.get("summary") or item.get("content") or "")[:200],
            memory_id=uuid.UUID(str(item["memory_id"])) if item.get("memory_id") else None,
            agent_run_id=agent_run_uuid,
        )

    return {
        "memory_written": memory_written,
        "nodes_executed": ["memory_writer"],
    }
