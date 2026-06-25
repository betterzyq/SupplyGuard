"""Graph query permission checks."""

from __future__ import annotations

from dataclasses import dataclass

from packages.authz.rbac import PermissionDecision, UserContext
from packages.graphrag.graph_schema import QUERY_TYPES


@dataclass(frozen=True)
class GraphPermissionContext:
    allowed_query_types: frozenset[str]
    supplier_scope: str | None = None


ROLE_QUERY_TYPES: dict[str, frozenset[str]] = {
    "admin": frozenset(QUERY_TYPES),
    "executive": frozenset(QUERY_TYPES),
    "procurement_manager": frozenset(
        {
            "supplier_impact",
            "product_dependency",
            "supplier_alternatives",
            "customer_order_dependency",
        }
    ),
    "logistics_manager": frozenset({"delivery_delay_impact", "supplier_impact"}),
    "quality_manager": frozenset({"quality_issue_trace", "supplier_impact"}),
    "finance_manager": frozenset({"supplier_impact"}),
    "external_supplier": frozenset(
        {
            "supplier_impact",
            "product_dependency",
            "supplier_alternatives",
            "delivery_delay_impact",
            "quality_issue_trace",
        }
    ),
}


def resolve_allowed_query_types(user_context: UserContext) -> frozenset[str]:
    allowed: set[str] = set()
    for role in user_context.roles:
        allowed.update(ROLE_QUERY_TYPES.get(role, frozenset()))
    if not allowed and "admin" in user_context.roles:
        allowed.update(QUERY_TYPES)
    return frozenset(allowed)


def resolve_supplier_scope(user_context: UserContext, supplier_code: str | None = None) -> str | None:
    if "external_supplier" in user_context.roles:
        return supplier_code or user_context.supplier_code
    return None


def check_graph_query_permission(
    user_context: UserContext,
    query_type: str,
    *,
    supplier_code: str | None = None,
    resolved_supplier_scope: str | None = None,
) -> PermissionDecision:
    if query_type not in QUERY_TYPES:
        return PermissionDecision(False, f"Unsupported graph query_type: {query_type}")

    allowed_types = resolve_allowed_query_types(user_context)
    if not allowed_types:
        return PermissionDecision(False, "Role is not permitted to query supply graph")

    if query_type not in allowed_types:
        return PermissionDecision(False, f"Role cannot execute graph query_type={query_type}")

    if user_context.is_external_supplier:
        scope = resolved_supplier_scope or supplier_code
        if not scope:
            return PermissionDecision(False, "External supplier scope is required")
        if supplier_code and supplier_code != scope:
            return PermissionDecision(False, "External supplier cannot query other suppliers")

    return PermissionDecision(True, "Graph query permitted")
