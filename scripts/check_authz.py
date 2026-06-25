#!/usr/bin/env python3
"""Authorization regression checks for seeded demo data."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from packages.authz.document_policy import can_access_document  # noqa: E402
from packages.authz.rbac import build_user_context  # noqa: E402
from packages.common.db.models import Document, User, UserRole  # noqa: E402
from packages.common.db.session import get_session_factory  # noqa: E402


async def _load_user(session, email: str) -> tuple[User, list[str]]:
    stmt = (
        select(User)
        .where(User.email == email)
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    user = (await session.execute(stmt)).scalar_one()
    roles = [link.role.name for link in user.user_roles]
    return user, roles


async def _load_document(session, slug: str) -> Document:
    stmt = select(Document).where(Document.metadata_.contains({"slug": slug}))
    return (await session.execute(stmt)).scalar_one()


def _ctx(user: User, roles: list[str]):
    return build_user_context(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        department=user.department,
        roles=roles,
        supplier_id=user.supplier_id,
    )


async def run_checks() -> int:
    session_factory = get_session_factory()
    failures = 0

    async with session_factory() as session:
        checks = [
            ("admin can access confidential", "admin@example.com", "confidential-supplier-contract", True),
            (
                "procurement_manager can access procurement confidential contract",
                "procurement_manager@example.com",
                "confidential-supplier-contract",
                True,
            ),
            (
                "procurement_staff cannot access confidential contract",
                "procurement_staff@example.com",
                "confidential-supplier-contract",
                False,
            ),
            (
                "logistics_manager can access logistics department report",
                "logistics_manager@example.com",
                "department-logistics-report",
                True,
            ),
            (
                "logistics_manager cannot access finance pricing terms",
                "logistics_manager@example.com",
                "finance-pricing-terms",
                False,
            ),
            (
                "finance_manager can access finance pricing terms",
                "finance_manager@example.com",
                "finance-pricing-terms",
                True,
            ),
            (
                "quality_manager can access quality report",
                "quality_manager@example.com",
                "quality-report",
                True,
            ),
            (
                "external_supplier can access own supplier_portal document",
                "supplier@example.com",
                "supplier-portal-sup001",
                True,
            ),
            (
                "external_supplier cannot access other supplier document",
                "supplier@example.com",
                "supplier-portal-sup002",
                False,
            ),
            (
                "executive can access executive_summary",
                "executive@example.com",
                "executive-summary",
                True,
            ),
            (
                "department must not grant access by itself",
                "logistics_manager@example.com",
                "department-only-trap",
                False,
            ),
        ]

        print("SupplyGuard authorization checks")
        print("=" * 60)
        for label, email, slug, expected in checks:
            user, roles = await _load_user(session, email)
            document = await _load_document(session, slug)
            decision = can_access_document(_ctx(user, roles), document)
            ok = decision.allowed is expected
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] {label}")
            print(f"       reason: {decision.reason}")
            if not ok:
                failures += 1

    print("=" * 60)
    if failures:
        print(f"Result: {failures} check(s) failed")
        return 1
    print("Result: all authorization checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_checks()))
