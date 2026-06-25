"""Agent tool execution node."""

from __future__ import annotations

from packages.agents.state import AgentState
from packages.mcp_servers.common.registry import execute_tool_call, format_tool_evidence_content


async def tool_node(state: AgentState) -> AgentState:
    if state.get("permission_decision") and not state["permission_decision"].allowed:
        return {"nodes_executed": ["tool_skipped"]}

    tool_name = state.get("tool_name")
    if not tool_name:
        return {
            "tool_evidence": [],
            "errors": ["tool_node invoked without tool_name"],
            "nodes_executed": ["tool"],
        }

    session = state["db_session"]
    user_context = state["user_context"]
    trace_id = state.get("trace_id") or ""
    agent_run_id = state.get("agent_run_id")

    execution = await execute_tool_call(
        session,
        user_context,
        tool_name,
        state.get("tool_input") or {},
        trace_id=trace_id,
        agent_run_id=agent_run_id,
    )

    citation = f"[tool:{tool_name}#{execution.tool_call_id}]"
    evidence_item = {
        "evidence_id": execution.tool_call_id or tool_name,
        "evidence_type": "tool_result",
        "source_id": tool_name,
        "source_title": f"Tool: {tool_name}",
        "content": format_tool_evidence_content(tool_name, execution.result),
        "score": 1.0 if execution.status == "success" else 0.5,
        "confidence": 0.95 if execution.status == "success" else 0.6,
        "permission_scope": execution.permission_decision,
        "citation": citation,
        "metadata": {
            "tool_name": tool_name,
            "tool_call_id": execution.tool_call_id,
            "status": execution.status,
            "approval_required": execution.approval_required,
        },
    }

    return {
        "tool_evidence": [evidence_item],
        "nodes_executed": ["tool"],
    }
