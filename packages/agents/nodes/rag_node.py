"""RAG retrieval node."""

from __future__ import annotations

import uuid

from packages.agents.state import AgentState
from packages.authz.audit import write_audit_log
from packages.observability.repositories.retrieval_log_repo import write_retrieval_log
from packages.rag.retriever import load_chunk_contents, retrieve_authorized_chunks


async def rag_node(state: AgentState) -> AgentState:
    if state.get("permission_decision") and not state["permission_decision"].allowed:
        return {"nodes_executed": ["rag_skipped"]}

    user_context = state["user_context"]
    session = state["db_session"]
    trace_id = state["trace_id"]
    query = state["query"]
    top_k = state.get("top_k", 5)
    chunk_size_config = state.get("chunk_size_config", 512)
    supplier_id = state.get("supplier_id")

    supplier_uuid: uuid.UUID | None = None
    if supplier_id:
        supplier_uuid = uuid.UUID(str(supplier_id))
    elif user_context.is_external_supplier and user_context.supplier_id:
        supplier_uuid = user_context.supplier_id

    chunks, filter_applied, latency_ms = await retrieve_authorized_chunks(
        user_context,
        query,
        top_k=top_k,
        chunk_size_config=chunk_size_config,
        doc_type=state.get("doc_type"),
        supplier_id=supplier_uuid,
    )
    chunks = await load_chunk_contents(session, chunks)

    results_payload = [
        {
            "document_id": str(item.document_id),
            "chunk_id": str(item.chunk_id),
            "chunk_index": item.chunk_index,
            "score": item.score,
            "title": item.title,
        }
        for item in chunks
    ]

    agent_run_id = state.get("agent_run_id")
    await write_retrieval_log(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        query=query,
        filter_applied=filter_applied,
        top_k=top_k,
        chunk_size_config=chunk_size_config,
        results=results_payload,
        latency_ms=latency_ms,
        result_count=len(chunks),
        agent_run_id=agent_run_id,
    )

    action = "rag_query_allowed" if chunks else "rag_query_no_evidence"
    await write_audit_log(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        action=action,
        resource_type="rag",
        resource_id=trace_id,
        permission_decision="allowed",
        reason=f"retrieved {len(chunks)} authorized chunks",
        ip_address=state.get("ip_address"),
        metadata={"query": query},
    )

    return {
        "retrieved_chunks": chunks,
        "evidence": [item.to_evidence_dict() for item in chunks],
        "nodes_executed": ["rag"],
        "latency_ms": latency_ms,
    }
