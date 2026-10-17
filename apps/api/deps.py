"""FastAPI dependencies."""

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.authz.audit import write_audit_log
from packages.authz.rbac import (
    UserContext,
    build_user_context,
    can_access_admin,
    require_any_role,
)
from packages.common.db.models.role import UserRole
from packages.common.db.models.user import User
from packages.common.db.session import get_db_session
from packages.common.security.jwt import verify_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = verify_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject"
        )

    stmt = (
        select(User)
        .where(User.id == UUID(user_id), User.is_active.is_(True))
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    if not user_to_context(user).is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has no active platform role",
        )
    request.state.user = user
    request.state.user_id = str(user.id)
    request.state.tenant_id = str(user.tenant_id)
    return user


def user_to_context(user: User) -> UserContext:
    roles = [link.role.name for link in user.user_roles if link.role is not None]
    return build_user_context(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        department=user.department,
        roles=roles,
        supplier_id=user.supplier_id,
    )


async def get_user_context(user: User = Depends(get_current_user)) -> UserContext:
    return user_to_context(user)


async def require_admin(
    request: Request,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> UserContext:
    decision = require_any_role(user_context, ["admin"])
    if not decision.allowed:
        await write_audit_log(
            session,
            tenant_id=user_context.tenant_id,
            user_id=user_context.user_id,
            action="permission_denied",
            resource_type="admin",
            resource_id="admin",
            permission_decision="denied",
            reason=decision.reason,
            ip_address=request.client.host if request.client else None,
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=decision.reason
        )
    if not can_access_admin(user_context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="admin access required"
        )
    return user_context
