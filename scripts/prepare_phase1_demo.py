#!/usr/bin/env python3
"""Add only missing two-role demo accounts. Never reset data or existing passwords."""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DEBUG"] = "false"

from sqlalchemy import select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from packages.authz.constants import normalize_roles  # noqa: E402
from packages.common.config import get_settings  # noqa: E402
from packages.common.db.models import Role, Tenant, User, UserRole  # noqa: E402
from packages.common.db.session import close_postgres, get_session_factory  # noqa: E402
from packages.common.security.password import hash_password  # noqa: E402


def validate_demo_database() -> None:
    url = make_url(get_settings().POSTGRES_URL)
    if (
        url.host not in {"localhost", "127.0.0.1"}
        or url.database != "supplyguard"
        or url.username != "supplyguard"
    ):
        raise RuntimeError(
            "Refusing demo setup: expected local supplyguard database and user"
        )
    if get_settings().APP_ENV not in {"development", "test"}:
        raise RuntimeError("Demo account setup is limited to development/test")


async def prepare() -> None:
    validate_demo_database()
    async with get_session_factory()() as session:
        async with session.begin():
            tenant = (
                await session.execute(select(Tenant).where(Tenant.code == "demo-mfg"))
            ).scalar_one_or_none()
            if tenant is None:
                raise RuntimeError(
                    "Existing demo-mfg tenant required; no seed/reset will be performed"
                )
            for role_name, email, full_name in (
                ("admin", "admin@example.com", "平台管理员"),
                ("enterprise", "enterprise@example.com", "企业演示用户"),
            ):
                user = (
                    await session.execute(
                        select(User)
                        .where(User.email == email)
                        .options(
                            selectinload(User.user_roles).selectinload(UserRole.role)
                        )
                    )
                ).scalar_one_or_none()
                if user:
                    roles = normalize_roles(
                        [link.role.name for link in user.user_roles]
                    )
                    if (
                        user.tenant_id != tenant.id
                        or not user.is_active
                        or roles != [role_name]
                    ):
                        raise RuntimeError(
                            f"Existing {email} conflicts with demo policy; no account overwrite"
                        )
                    print(
                        f"PRESERVED {email}: role={role_name}; existing password unchanged"
                    )
                    continue
                role = (
                    await session.execute(
                        select(Role).where(
                            Role.tenant_id == tenant.id, Role.name == role_name
                        )
                    )
                ).scalar_one_or_none()
                if role is None:
                    role = Role(
                        tenant_id=tenant.id,
                        name=role_name,
                        description="SupplyGuard enterprise-v2",
                    )
                    session.add(role)
                    await session.flush()
                user = User(
                    tenant_id=tenant.id,
                    email=email,
                    full_name=full_name,
                    department="enterprise",
                    password_hash=hash_password("password123"),
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                session.add(UserRole(user_id=user.id, role_id=role.id))
                print(f"CREATED {email}: role={role_name}")


if __name__ == "__main__":

    async def main():
        try:
            await prepare()
        finally:
            await close_postgres()

    asyncio.run(main())
