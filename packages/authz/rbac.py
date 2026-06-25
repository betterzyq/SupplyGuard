"""RBAC helpers and user context."""

from dataclasses import dataclass, field
from uuid import UUID

from packages.authz.constants import get_max_security_rank_for_roles


@dataclass
class PermissionDecision:
    allowed: bool
    reason: str


@dataclass
class UserContext:
    user_id: UUID
    tenant_id: UUID
    email: str
    department: str
    roles: list[str] = field(default_factory=list)
    supplier_id: UUID | None = None
    max_security_rank: int = 0

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    @property
    def is_external_supplier(self) -> bool:
        return "external_supplier" in self.roles


def build_user_context(
    *,
    user_id: UUID,
    tenant_id: UUID,
    email: str,
    department: str,
    roles: list[str],
    supplier_id: UUID | None = None,
) -> UserContext:
    return UserContext(
        user_id=user_id,
        tenant_id=tenant_id,
        email=email,
        department=department,
        roles=roles,
        supplier_id=supplier_id,
        max_security_rank=get_max_security_rank_for_roles(roles),
    )


def has_role(user_context: UserContext, role: str) -> bool:
    return role in user_context.roles


def require_any_role(user_context: UserContext, roles: list[str]) -> PermissionDecision:
    if user_context.is_admin:
        return PermissionDecision(True, "admin bypass")
    if set(user_context.roles) & set(roles):
        return PermissionDecision(True, f"matched roles: {sorted(set(user_context.roles) & set(roles))}")
    return PermissionDecision(False, f"requires one of {roles}")


def get_max_security_rank(user_context: UserContext) -> int:
    return user_context.max_security_rank


def can_access_admin(user_context: UserContext) -> bool:
    return user_context.is_admin


def can_upload_document(user_context: UserContext) -> bool:
    if user_context.is_admin:
        return True
    return bool(set(user_context.roles) & {"procurement_manager", "finance_manager", "quality_manager"})


def can_run_benchmark(user_context: UserContext) -> bool:
    return user_context.is_admin


def can_call_tool(user_context: UserContext, tool_name: str) -> PermissionDecision:
    if user_context.is_admin:
        return PermissionDecision(True, "admin tool access")
    if tool_name.startswith("supplier_") and user_context.is_external_supplier:
        return PermissionDecision(True, "supplier scoped tool")
    if not user_context.is_external_supplier:
        return PermissionDecision(True, f"internal tool access: {tool_name}")
    return PermissionDecision(False, f"tool denied for external supplier: {tool_name}")
