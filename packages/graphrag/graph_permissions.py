"""All enterprise members can query their tenant's business graph."""

from dataclasses import dataclass

from packages.authz.rbac import PermissionDecision, UserContext
from packages.graphrag.graph_schema import QUERY_TYPES


@dataclass(frozen=True)
class GraphPermissionContext:
    allowed_query_types: frozenset[str]
    supplier_scope: str | None = None


ROLE_QUERY_TYPES = {
    "admin": frozenset(QUERY_TYPES),
    "enterprise": frozenset(QUERY_TYPES),
}


def resolve_allowed_query_types(user_context: UserContext) -> frozenset[str]:
    return frozenset(QUERY_TYPES) if user_context.is_member else frozenset()


def resolve_supplier_scope(
    user_context: UserContext, supplier_code: str | None = None
) -> str | None:
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
    return PermissionDecision(
        user_context.is_member, "enterprise-v2 tenant graph access"
    )
