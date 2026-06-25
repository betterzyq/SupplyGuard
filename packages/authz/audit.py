"""Audit log repository."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.audit_log import AuditLog


async def write_audit_log(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    action: str,
    resource_type: str,
    permission_decision: str,
    reason: str,
    user_id: uuid.UUID | None = None,
    trace_id: str | None = None,
    resource_id: str | None = None,
    ip_address: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        user_id=user_id,
        trace_id=trace_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        permission_decision=permission_decision,
        reason=reason,
        ip_address=ip_address,
        metadata_=metadata or {},
    )
    session.add(entry)
    await session.flush()
    return entry
