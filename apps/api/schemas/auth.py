"""Auth API schemas."""

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserInfo(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    roles: list[str]
    department: str
    tenant_id: UUID
    supplier_id: UUID | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo


class PermissionsResponse(BaseModel):
    policy_version: str = "enterprise-v2"
    roles: list[str]
    max_security_rank: int
    can_access_admin: bool
    can_upload_document: bool
    can_run_benchmark: bool
