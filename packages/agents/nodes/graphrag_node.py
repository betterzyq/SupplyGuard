"""GraphRAG retrieval node."""

from __future__ import annotations

import uuid

from packages.agents.state import AgentState
from packages.authz.audit import write_audit_log
from packages.graphrag.graph_retriever import execute_graph_query


async def graphrag_node(state: AgentState) -> AgentState:
    if state.get("permission_decision") and not state["permission_decision"].allowed:
        return {"nodes_executed": ["graphrag_skipped"]}

    user_context = state["user_context"]
    session = state["db_session"]
    trace_id = state["trace_id"]
    query = state["query"]
    query_type = state.get("graph_query_type") or "supplier_impact"
    entity_code = state.get("graph_entity_code")
    top_k = state.get("top_k", 20)
    route_mode = state.get("route_mode") or "graphrag"

    agent_run_id = state.get("agent_run_id")
    agent_run_uuid = uuid.UUID(agent_run_id) if agent_run_id else None

    result = await execute_graph_query(
        user_context,
        query=query,
        query_type=query_type,
        entity_code=entity_code,
        top_k=top_k,
        trace_id=trace_id,
        agent_run_id=agent_run_uuid,
        session=session,
        ip_address=state.get("ip_address"),
    )

    if result.permission_decision == "denied":
        await write_audit_log(
            session,
            tenant_id=user_context.tenant_id,
            user_id=user_context.user_id,
            trace_id=trace_id,
            action="graphrag_node_denied",
            resource_type="graphrag",
            resource_id=trace_id,
            permission_decision="denied",
            reason=result.error_message or "graph query denied",
            ip_address=state.get("ip_address"),
            metadata={"query_type": query_type},
        )
        if route_mode == "hybrid":
            return {
                "graph_result": result,
                "graph_paths": [],
                "graph_evidence": [],
                "nodes_executed": ["graphrag"],
            }
        return {
            "graph_result": result,
            "graph_paths": [],
            "graph_evidence": [],
            "status": "blocked",
            "draft_answer": "您无权访问该供应链图谱查询。",
            "nodes_executed": ["graphrag"],
        }

    graph_evidence = [
        {
            "type": "graph_path",
            "ref": path.to_dict()["graph_path_ref"],
            "path_text": path.path_text,
            "template_id": path.template_id,
        }
        for path in result.graph_paths
    ]

    return {
        "graph_result": result,
        "graph_paths": result.graph_paths,
        "graph_evidence": graph_evidence,
        "graph_query_type": query_type,
        "graph_entity_code": entity_code,
        "nodes_executed": ["graphrag"],
    }
