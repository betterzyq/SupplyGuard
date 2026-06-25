"""LangGraph workflow assembly."""

from __future__ import annotations

import time
from typing import Any

from langgraph.graph import END, StateGraph
from sqlalchemy.ext.asyncio import AsyncSession

from packages.agents.nodes.evidence_aggregator_node import evidence_aggregator_node
from packages.agents.nodes.graphrag_node import graphrag_node
from packages.agents.nodes.memory_node import memory_node
from packages.agents.nodes.memory_writer_node import memory_writer_node
from packages.agents.nodes.permission_node import permission_node
from packages.agents.nodes.rag_node import rag_node
from packages.agents.nodes.report_node import report_node
from packages.agents.nodes.review_node import review_node
from packages.agents.nodes.router_node import router_node
from packages.agents.nodes.tool_node import tool_node
from packages.agents.state import AgentState
from packages.authz.rbac import UserContext
from packages.observability.callbacks import get_langgraph_callbacks, setup_langsmith_tracing, wrap_agent_node
from packages.observability.repositories.agent_run_repo import create_agent_run, finalize_agent_run
from packages.observability.trace_context import get_request_id, resolve_trace_id, set_trace_id


def _route_after_permission(state: AgentState) -> str:
    decision = state.get("permission_decision")
    if decision and not decision.allowed:
        return "review"
    return "router"


def _route_after_router(state: AgentState) -> str:
    route_mode = state.get("route_mode") or "rag"
    if route_mode == "tool":
        return "tool"
    if route_mode in {"graphrag", "hybrid", "memory_rag"}:
        return "graphrag"
    if route_mode == "memory":
        return "memory"
    return "rag"


def _route_after_graphrag(state: AgentState) -> str:
    route_mode = state.get("route_mode") or "rag"
    if route_mode in {"hybrid", "memory_rag"} and state.get("status") != "blocked":
        return "rag"
    if state.get("use_memory", True):
        return "memory"
    return "aggregator"


def _route_after_rag(state: AgentState) -> str:
    if state.get("use_memory", True):
        return "memory"
    return "aggregator"


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("permission", wrap_agent_node("permission", permission_node))
    graph.add_node("router", wrap_agent_node("router", router_node))
    graph.add_node("tool", wrap_agent_node("tool", tool_node))
    graph.add_node("graphrag", wrap_agent_node("graphrag", graphrag_node))
    graph.add_node("rag", wrap_agent_node("rag", rag_node))
    graph.add_node("memory", wrap_agent_node("memory", memory_node))
    graph.add_node("aggregator", wrap_agent_node("aggregator", evidence_aggregator_node))
    graph.add_node("report", wrap_agent_node("report", report_node))
    graph.add_node("review", wrap_agent_node("review", review_node))
    graph.add_node("memory_writer", wrap_agent_node("memory_writer", memory_writer_node))

    graph.set_entry_point("permission")
    graph.add_conditional_edges(
        "permission",
        _route_after_permission,
        {"router": "router", "review": "review"},
    )
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {"tool": "tool", "graphrag": "graphrag", "rag": "rag", "memory": "memory"},
    )
    graph.add_edge("tool", "aggregator")
    graph.add_conditional_edges(
        "graphrag",
        _route_after_graphrag,
        {"rag": "rag", "memory": "memory", "aggregator": "aggregator"},
    )
    graph.add_conditional_edges(
        "rag",
        _route_after_rag,
        {"memory": "memory", "aggregator": "aggregator"},
    )
    graph.add_edge("memory", "aggregator")
    graph.add_edge("aggregator", "report")
    graph.add_edge("report", "review")
    graph.add_edge("review", "memory_writer")
    graph.add_edge("memory_writer", END)
    return graph.compile()


async def run_chat_workflow(
    session: AsyncSession,
    user_context: UserContext,
    query: str,
    *,
    session_id: str | None = None,
    top_k: int = 5,
    chunk_size_config: int = 512,
    doc_type: str | None = None,
    supplier_id: str | None = None,
    ip_address: str | None = None,
    use_memory: bool = True,
    trace_id: str | None = None,
) -> dict[str, Any]:
    setup_langsmith_tracing()
    trace_id = resolve_trace_id(header_value=trace_id)
    set_trace_id(trace_id)
    session_id = session_id or trace_id
    started = time.perf_counter()

    agent_run = await create_agent_run(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        session_id=session_id,
        query=query,
        request_id=get_request_id(),
    )

    initial_state: AgentState = {
        "query": query,
        "user_context": user_context,
        "trace_id": trace_id,
        "session_id": session_id,
        "agent_run_id": str(agent_run.id),
        "top_k": top_k,
        "chunk_size_config": chunk_size_config,
        "doc_type": doc_type,
        "supplier_id": supplier_id,
        "ip_address": ip_address,
        "use_memory": use_memory,
        "db_session": session,
        "errors": [],
        "nodes_executed": [],
        "memory_used": [],
        "memory_written": [],
    }

    graph = build_agent_graph()
    callbacks = get_langgraph_callbacks()
    config = {"callbacks": callbacks} if callbacks else {}
    try:
        final_state = await graph.ainvoke(initial_state, config=config)
        latency_ms = int((time.perf_counter() - started) * 1000)
        citations = [item.to_dict() for item in final_state.get("citations") or []]
        status = final_state.get("status") or "completed"
        if status in {"answered", "no_evidence"}:
            run_status = "completed"
        elif status == "blocked":
            run_status = "blocked"
        else:
            run_status = "completed"

        memory_used = [
            item
            for item in (final_state.get("memory_evidence") or [])
            if item.get("citation")
        ]

        await finalize_agent_run(
            session,
            agent_run,
            status=run_status,
            final_answer=final_state.get("final_answer"),
            citations=citations,
            token_usage=final_state.get("token_usage") or {},
            latency_ms=latency_ms,
            nodes_executed=final_state.get("nodes_executed") or [],
        )
        await session.commit()

        return {
            "answer": final_state.get("final_answer") or "",
            "citations": citations,
            "trace_id": trace_id,
            "agent_run_id": str(agent_run.id),
            "nodes_executed": final_state.get("nodes_executed") or [],
            "token_usage": final_state.get("token_usage") or {},
            "status": run_status,
            "route_mode": final_state.get("route_mode"),
            "graph_paths": [
                path.to_dict() if hasattr(path, "to_dict") else path
                for path in (final_state.get("graph_paths") or [])
            ],
            "memory_used": memory_used,
            "memory_written": final_state.get("memory_written") or [],
            "context_budget": final_state.get("context_budget") or {},
        }
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        await finalize_agent_run(
            session,
            agent_run,
            status="failed",
            final_answer=None,
            citations=[],
            token_usage={},
            latency_ms=latency_ms,
            nodes_executed=["failed"],
            error_message=str(exc),
        )
        await session.commit()
        raise
