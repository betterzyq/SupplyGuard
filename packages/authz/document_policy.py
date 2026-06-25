"""Document access policy."""

from uuid import UUID

from packages.authz.rbac import PermissionDecision, UserContext


class DocumentLike:
    tenant_id: UUID
    security_level_rank: int
    access_scope: str
    department: str
    allowed_roles: list
    allowed_users: list
    supplier_id: UUID | None


def _allowed(user_context: UserContext, reason: str) -> PermissionDecision:
    return PermissionDecision(True, reason)


def _denied(user_context: UserContext, reason: str) -> PermissionDecision:
    return PermissionDecision(False, reason)


def can_access_document(user_context: UserContext, document: DocumentLike) -> PermissionDecision:
    if document.tenant_id != user_context.tenant_id:
        return _denied(user_context, "tenant mismatch")

    if user_context.is_admin:
        return _allowed(user_context, "admin full tenant access")

    if document.security_level_rank > user_context.max_security_rank:
        return _denied(
            user_context,
            f"security rank {document.security_level_rank} exceeds user max {user_context.max_security_rank}",
        )

    scope = document.access_scope

    if scope == "public":
        return _allowed(user_context, "public scope")

    if scope == "department":
        if document.department == user_context.department:
            return _allowed(user_context, "department scope matched")
        return _denied(user_context, "department scope mismatch")

    if scope == "role_based":
        doc_roles = set(document.allowed_roles or [])
        if doc_roles & set(user_context.roles):
            return _allowed(user_context, "role_based scope matched")
        return _denied(user_context, "role_based scope no matching role")

    if scope == "user_whitelist":
        allowed_users = {str(item) for item in (document.allowed_users or [])}
        if str(user_context.user_id) in allowed_users:
            return _allowed(user_context, "user whitelist matched")
        return _denied(user_context, "user not in whitelist")

    if scope == "supplier_portal":
        supplier_check = check_supplier_scope(user_context, document.supplier_id)
        if supplier_check.allowed:
            return _allowed(user_context, supplier_check.reason)
        return _denied(user_context, supplier_check.reason)

    if scope == "executive_summary":
        if user_context.is_admin or "executive" in user_context.roles:
            return _allowed(user_context, "executive summary scope")
        return _denied(user_context, "executive summary requires executive or admin role")

    return _denied(user_context, f"unknown access_scope: {scope}")


def can_access_chunk(user_context: UserContext, chunk: DocumentLike) -> PermissionDecision:
    return can_access_document(user_context, chunk)


def explain_document_access(user_context: UserContext, document: DocumentLike) -> dict:
    decision = can_access_document(user_context, document)
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "tenant_id": str(document.tenant_id),
        "access_scope": document.access_scope,
        "security_level_rank": document.security_level_rank,
        "user_max_security_rank": user_context.max_security_rank,
        "user_roles": user_context.roles,
        "user_department": user_context.department,
    }


def check_supplier_scope(user_context: UserContext, supplier_id: UUID | None) -> PermissionDecision:
    if not user_context.is_external_supplier:
        return PermissionDecision(False, "supplier_portal scope requires external_supplier role")
    if user_context.supplier_id is None:
        return PermissionDecision(False, "external supplier missing supplier_id")
    if supplier_id is None:
        return PermissionDecision(False, "document missing supplier_id")
    if user_context.supplier_id == supplier_id:
        return PermissionDecision(True, "supplier portal scope matched")
    return PermissionDecision(False, "supplier portal supplier mismatch")
