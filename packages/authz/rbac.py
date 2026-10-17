"""RBAC helpers and user context."""

from dataclasses import dataclass, field
from uuid import UUID

from packages.authz.constants import get_max_security_rank_for_roles, normalize_roles


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

    def __post_init__(self) -> None:
        self.roles = normalize_roles(self.roles)
        self.max_security_rank = get_max_security_rank_for_roles(self.roles)

    @property
    def is_member(self) -> bool:
        return bool(set(self.roles) & {"admin", "enterprise"})

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

    @property
    def is_external_supplier(self) -> bool:
        return False  # Retired portal; retained for legacy graph/memory adapters.


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
        return PermissionDecision(
            True, f"matched roles: {sorted(set(user_context.roles) & set(roles))}"
        )
    return PermissionDecision(False, f"requires one of {roles}")


def get_max_security_rank(user_context: UserContext) -> int:
    return user_context.max_security_rank


def can_access_admin(user_context: UserContext) -> bool:
    return user_context.is_admin


def can_upload_document(user_context: UserContext) -> bool:
    return user_context.is_member


def can_run_benchmark(user_context: UserContext) -> bool:
    return user_context.is_admin


def can_call_tool(user_context: UserContext, tool_name: str) -> PermissionDecision:
    from packages.authz.tool_policy import check_tool_permission

    result = check_tool_permission(user_context, tool_name)
    return PermissionDecision(result.allowed, result.reason)
