"""Authentication routes."""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.deps import get_current_user, user_to_context
from apps.api.schemas.auth import LoginRequest, LoginResponse, UserInfo
from packages.authz.audit import write_audit_log
from packages.common.db.models.role import UserRole
from packages.common.db.models.user import User
from packages.common.db.session import get_db_session
from packages.common.security.jwt import create_access_token
from packages.common.security.password import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_info(user: User) -> UserInfo:
    ctx = user_to_context(user)
    return UserInfo(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=ctx.roles,
        department=user.department,
        tenant_id=user.tenant_id,
        supplier_id=user.supplier_id,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    payload: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    stmt = (
        select(User)
        .where(User.email == payload.email)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    ip_address = request.client.host if request.client else None

    if user is None or not verify_password(payload.password, user.password_hash):
        tenant_id = user.tenant_id if user else None
        if tenant_id is not None:
            await write_audit_log(
                session,
                tenant_id=tenant_id,
                user_id=user.id if user else None,
                action="login_failure",
                resource_type="auth",
                resource_id=payload.email,
                permission_decision="denied",
                reason="invalid credentials",
                ip_address=ip_address,
            )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive"
        )

    ctx = user_to_context(user)
    if not ctx.is_member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has no active platform role",
        )
    user.last_login_at = datetime.now(UTC)
    token = create_access_token(
        subject=str(user.id),
        claims={
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "roles": ctx.roles,
        },
    )

    await write_audit_log(
        session,
        tenant_id=user.tenant_id,
        user_id=user.id,
        action="login_success",
        resource_type="auth",
        resource_id=str(user.id),
        permission_decision="allowed",
        reason="login successful",
        ip_address=ip_address,
    )
    await session.commit()

    return LoginResponse(access_token=token, user=_user_info(user))


@router.get("/me", response_model=UserInfo)
async def auth_me(user: User = Depends(get_current_user)) -> UserInfo:
    return _user_info(user)
