"""Tool Permission Guard."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from packages.authz.rbac import UserContext

ALL_TOOLS = {
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

HIGH_RISK_TOOLS = frozenset({"export_risk_report", "export_benchmark_results"})

ROLE_TOOLS: dict[str, frozenset[str]] = {
    "admin": ALL_TOOLS,
    "procurement_manager": frozenset(
        {
            "query_supplier_profile",
            "query_supplier_risk_events",
            "query_supplier_delivery_history",
            "query_supplier_contract_summary",
            "export_risk_report",
        }
    ),
    "procurement_staff": frozenset(
        {
            "query_supplier_profile",
            "query_supplier_delivery_history",
        }
    ),
    "logistics_manager": frozenset(
        {
            "query_delivery_status",
            "query_delay_events",
            "query_route_info",
        }
    ),
    "finance_manager": frozenset(
        {
            "query_supplier_profile",
            "query_supplier_contract_summary",
        }
    ),
    "quality_manager": frozenset(
        {
            "query_supplier_profile",
            "query_supplier_risk_events",
        }
    ),
    "executive": frozenset(
        {
            "query_supplier_profile",
            "query_supplier_risk_events",
            "export_risk_report",
            "export_benchmark_results",
        }
    ),
    "external_supplier": frozenset(
        {
            "query_supplier_profile",
            "query_delivery_status",
        }
    ),
}


@dataclass(frozen=True)
class ToolPermissionResult:
    allowed: bool
    reason: str
    approval_required: bool = False
    permission_decision: str = "denied"


def _role_allowed_tools(user_context: UserContext) -> frozenset[str]:
    if user_context.is_admin:
        return ALL_TOOLS
    allowed: set[str] = set()
    for role in user_context.roles:
        allowed |= ROLE_TOOLS.get(role, frozenset())
    return frozenset(allowed)


def check_tool_permission(
    user_context: UserContext,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
) -> ToolPermissionResult:
    tool_input = tool_input or {}
    if tool_name not in ALL_TOOLS:
        return ToolPermissionResult(False, f"unknown tool: {tool_name}", permission_decision="denied")

    allowed_tools = _role_allowed_tools(user_context)
    if tool_name not in allowed_tools:
        return ToolPermissionResult(
            False,
            f"role {user_context.roles} cannot call {tool_name}",
            permission_decision="denied",
        )

    if tool_name in HIGH_RISK_TOOLS:
        return ToolPermissionResult(
            True,
            "high-risk tool requires approval",
            approval_required=True,
            permission_decision="approval_required",
        )

    if user_context.is_external_supplier:
        supplier_code = str(tool_input.get("supplier_code") or tool_input.get("supplier_id") or "").upper()
        if supplier_code.startswith("S") and not supplier_code.startswith("SUP-"):
            supplier_code = f"SUP-{supplier_code.lstrip('S').zfill(3)}"
        if user_context.supplier_id and supplier_code:
            # Scope check deferred to executor with DB lookup; block obvious cross-supplier codes in input
            pass
        elif tool_name == "query_supplier_profile" and not supplier_code:
            return ToolPermissionResult(
                False,
                "external_supplier must specify own supplier_code",
                permission_decision="denied",
            )

    return ToolPermissionResult(True, "allowed", permission_decision="allowed")


async def enforce_supplier_scope(
    session,
    user_context: UserContext,
    supplier_code: str | None,
) -> tuple[bool, str, str | None]:
    """Return (ok, reason, normalized_code)."""
    if not user_context.is_external_supplier:
        return True, "internal user", supplier_code
    if not user_context.supplier_id:
        return False, "external_supplier missing supplier_id", supplier_code
    from sqlalchemy import select

    from packages.common.db.models.supplier import Supplier

    own = (
        await session.execute(select(Supplier.code).where(Supplier.id == user_context.supplier_id))
    ).scalar_one_or_none()
    if not own:
        return False, "supplier not found", supplier_code
    if supplier_code and supplier_code.upper() != own.upper():
        return False, f"external_supplier can only access {own}", own
    return True, "scoped", own
