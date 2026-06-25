"""Admin routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import require_admin
from packages.authz.rbac import UserContext
from packages.common.db.models.audit_log import AuditLog
from packages.common.db.session import get_db_session

router = APIRouter(prefix="/admin", tags=["admin"])


class AuditLogItem(BaseModel):
    id: UUID
    tenant_id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    permission_decision: str
    reason: str
    ip_address: str | None
    created_at: object


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem]
    total: int


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    _: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> AuditLogListResponse:
    stmt = (
        select(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(stmt)
    items = result.scalars().all()
    return AuditLogListResponse(
        items=[
            AuditLogItem(
                id=item.id,
                tenant_id=item.tenant_id,
                user_id=item.user_id,
                action=item.action,
                resource_type=item.resource_type,
                resource_id=item.resource_id,
                permission_decision=item.permission_decision,
                reason=item.reason,
                ip_address=item.ip_address,
                created_at=item.created_at,
            )
            for item in items
        ],
        total=len(items),
    )
