"""MCP permission helpers (delegates to authz tool_policy)."""

from __future__ import annotations

from typing import Any

from packages.authz.rbac import UserContext
from packages.authz.tool_policy import (
    ALL_TOOLS,
    HIGH_RISK_TOOLS,
    ROLE_TOOLS,
    ToolPermissionResult,
    check_tool_permission,
    enforce_supplier_scope,
)

__all__ = [
    "ALL_TOOLS",
    "HIGH_RISK_TOOLS",
    "ROLE_TOOLS",
    "ToolPermissionResult",
    "check_tool_permission",
    "enforce_supplier_scope",
    "list_allowed_tools",
]


def list_allowed_tools(user_context: UserContext) -> list[str]:
    if user_context.is_admin:
        return sorted(ALL_TOOLS)
    allowed: set[str] = set()
    for role in user_context.roles:
        allowed |= ROLE_TOOLS.get(role, frozenset())
    return sorted(allowed)


def is_tool_allowed(user_context: UserContext, tool_name: str, tool_input: dict[str, Any] | None = None) -> bool:
    return check_tool_permission(user_context, tool_name, tool_input).allowed
