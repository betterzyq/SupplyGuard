"""User routes."""

from fastapi import APIRouter, Depends

from apps.api.deps import get_current_user, get_user_context
from apps.api.routers.v1.auth import _user_info
from apps.api.schemas.auth import PermissionsResponse, UserInfo
from packages.authz.rbac import can_run_benchmark, can_upload_document
from packages.common.db.models.user import User

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserInfo)
async def users_me(user: User = Depends(get_current_user)) -> UserInfo:
    return _user_info(user)


@router.get("/me/permissions", response_model=PermissionsResponse)
async def users_permissions(user_context=Depends(get_user_context)) -> PermissionsResponse:
    return PermissionsResponse(
        roles=user_context.roles,
        max_security_rank=user_context.max_security_rank,
        can_access_admin=user_context.is_admin,
        can_upload_document=can_upload_document(user_context),
        can_run_benchmark=can_run_benchmark(user_context),
    )
