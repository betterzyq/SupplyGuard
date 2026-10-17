"""Business documents are shared within a tenant under enterprise-v2."""

from uuid import UUID

from packages.authz.rbac import PermissionDecision, UserContext


class DocumentLike:
    tenant_id: UUID


def can_access_document(
    user_context: UserContext, document: DocumentLike
) -> PermissionDecision:
    if document.tenant_id != user_context.tenant_id:
        return PermissionDecision(False, "tenant mismatch")
    if not user_context.is_member:
        return PermissionDecision(False, "enterprise membership required")
    return PermissionDecision(True, "enterprise-v2: shared within tenant")


def can_access_chunk(
    user_context: UserContext, chunk: DocumentLike
) -> PermissionDecision:
    return can_access_document(user_context, chunk)


def explain_document_access(user_context: UserContext, document: DocumentLike) -> dict:
    decision = can_access_document(user_context, document)
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "tenant_id": str(document.tenant_id),
        "user_roles": user_context.roles,
        "policy_version": "enterprise-v2",
    }


def check_supplier_scope(
    user_context: UserContext, supplier_id: UUID | None
) -> PermissionDecision:
    return PermissionDecision(user_context.is_member, "enterprise-v2 membership")
