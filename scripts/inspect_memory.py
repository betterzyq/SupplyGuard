#!/usr/bin/env python3
"""Inspect long-term and session memory."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from packages.authz.rbac import build_user_context
from packages.common.db.models.memory import Memory
from packages.common.db.models.user import User
from packages.common.db.session import get_session_factory
from packages.memory.long_term import list_user_memories


async def inspect() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        total = (await session.execute(select(func.count()).select_from(Memory))).scalar_one()
        print(f"long_term_memories: {total}")

        user = (
            await session.execute(select(User).where(User.email == "procurement_manager@example.com"))
        ).scalar_one_or_none()
        if user:
            ctx = build_user_context(
                user_id=user.id,
                tenant_id=user.tenant_id,
                email=user.email,
                department=user.department,
                roles=["procurement_manager"],
            )
            records = await list_user_memories(session, ctx, limit=5)
            for record in records:
                print(f"- {record.memory_type}: {record.summary or record.content[:80]}")


def main() -> None:
    asyncio.run(inspect())


if __name__ == "__main__":
    main()
