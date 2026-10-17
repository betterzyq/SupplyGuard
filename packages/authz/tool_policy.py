"""Two-role tool policy. Business reads need no per-department approval."""

from dataclasses import dataclass
from typing import Any

from packages.authz.rbac import UserContext

ALL_TOOLS = frozenset(
    {
        "query_supplier_profile",
        "query_supplier_risk_events",
        "query_supplier_delivery_history",
        "query_supplier_contract_summary",
        "query_delivery_status",
        "query_delay_events",
        "query_route_info",
        "export_risk_report",
        "export_benchmark_results",
    }
)
HIGH_RISK_TOOLS = frozenset()
ROLE_TOOLS = {
    "admin": ALL_TOOLS,
    "enterprise": ALL_TOOLS - {"export_benchmark_results"},
}


@dataclass(frozen=True)
class ToolPermissionResult:
    allowed: bool
    reason: str
    approval_required: bool = False
    permission_decision: str = "denied"


def check_tool_permission(
    user_context: UserContext,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
) -> ToolPermissionResult:
    if tool_name not in ALL_TOOLS:
        return ToolPermissionResult(False, f"unknown tool: {tool_name}")
    allowed = any(tool_name in ROLE_TOOLS.get(role, ()) for role in user_context.roles)
    return ToolPermissionResult(
        allowed,
        (
            "enterprise-v2 tool access"
            if allowed
            else "administrator required or no membership"
        ),
        permission_decision="allowed" if allowed else "denied",
    )


async def enforce_supplier_scope(
    session, user_context: UserContext, supplier_code: str | None
):
    # Every executor must still filter DB reads by tenant_id.
    return user_context.is_member, "enterprise-v2 membership", supplier_code
