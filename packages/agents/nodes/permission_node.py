"""Permission node."""

from __future__ import annotations

from packages.agents.state import AgentState
from packages.authz.audit import write_audit_log
from packages.authz.rbac import PermissionDecision
from packages.rag.prompts import NO_PERMISSION_ANSWER


async def permission_node(state: AgentState) -> AgentState:
    user_context = state["user_context"]
    session = state["db_session"]
    trace_id = state["trace_id"]

    if not user_context:
        decision = PermissionDecision(False, "missing user context")
    elif not user_context.is_member:
        decision = PermissionDecision(False, "enterprise membership required")
    else:
        decision = PermissionDecision(True, "query permitted for authenticated user")

    await write_audit_log(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        action=(
            "chat_permission_allowed" if decision.allowed else "chat_permission_denied"
        ),
        resource_type="chat",
        resource_id=trace_id,
        permission_decision="allowed" if decision.allowed else "denied",
        reason=decision.reason,
        ip_address=state.get("ip_address"),
        metadata={"query": state["query"]},
    )

    updates: AgentState = {
        "permission_decision": decision,
        "nodes_executed": ["permission"],
    }
    if not decision.allowed:
        updates["draft_answer"] = NO_PERMISSION_ANSWER
        updates["final_answer"] = NO_PERMISSION_ANSWER
        updates["status"] = "blocked"
        updates["review_passed"] = True
    return updates
