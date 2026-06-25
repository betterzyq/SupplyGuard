#!/usr/bin/env python3
"""Memory and context management smoke test."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import httpx
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.authz.rbac import build_user_context  # noqa: E402
from packages.common.db.models.memory import Memory  # noqa: E402
from packages.common.db.models.user import User  # noqa: E402
from packages.common.db.session import get_session_factory  # noqa: E402
from packages.memory.long_term import create_memory, list_user_memories  # noqa: E402
from packages.memory.memory_policy import should_write_memory  # noqa: E402
from packages.memory.memory_types import MemoryScope, MemoryWriteEvent  # noqa: E402
from packages.memory.short_term import append_message, clear_session, get_recent_messages, now_iso  # noqa: E402
from packages.memory.memory_types import SessionMessage  # noqa: E402

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PASSWORD = "password123"


def record(name: str, passed: bool, detail: str = "") -> bool:
    status = "PASS" if passed else "FAIL"
    suffix = f" ({detail})" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return passed


async def login(client: httpx.AsyncClient, email: str) -> str:
    response = await client.post(
        f"{API_BASE}/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def chat(
    client: httpx.AsyncClient,
    token: str,
    query: str,
    *,
    session_id: str | None = None,
) -> dict:
    response = await client.post(
        f"{API_BASE}/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "session_id": session_id, "top_k": 5, "use_memory": True},
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()


async def main() -> int:
    passed = 0
    total = 0
    session_factory = get_session_factory()

    async with session_factory() as db:
        user_a = (await db.execute(select(User).where(User.email == "procurement_manager@example.com"))).scalar_one()
        user_b = (await db.execute(select(User).where(User.email == "logistics_manager@example.com"))).scalar_one()
        supplier_user = (await db.execute(select(User).where(User.email == "supplier@example.com"))).scalar_one()
        ctx_a = build_user_context(
            user_id=user_a.id,
            tenant_id=user_a.tenant_id,
            email=user_a.email,
            department=user_a.department,
            roles=["procurement_manager"],
        )
        ctx_b = build_user_context(
            user_id=user_b.id,
            tenant_id=user_b.tenant_id,
            email=user_b.email,
            department=user_b.department,
            roles=["logistics_manager"],
        )

    session_id = f"mem-smoke-{uuid.uuid4().hex[:8]}"
    tenant_id = str(user_a.tenant_id)
    user_id = str(user_a.id)

    await append_message(
        tenant_id,
        user_id,
        session_id,
        SessionMessage(role="user", content="hello", timestamp=now_iso(), entities={"supplier": "SUP-001"}),
    )
    messages = await get_recent_messages(tenant_id, user_id, session_id)
    total += 1
    if record("redis session write/read", len(messages) >= 1, f"count={len(messages)}"):
        passed += 1

    async with session_factory() as db:
        row = await create_memory(
            db,
            ctx_a,
            MemoryWriteEvent(
                content="用户偏好：报告使用简洁 executive summary 风格",
                memory_type="preference",
                scope=MemoryScope.USER,
                is_user_explicit=True,
            ),
        )
        await db.commit()
    total += 1
    if record("long-term memory write", row is not None):
        passed += 1

    async with session_factory() as db:
        own = await list_user_memories(db, ctx_a, limit=20)
    total += 1
    if record("user reads own memory", len(own) >= 1):
        passed += 1

    async with session_factory() as db:
        other = await list_user_memories(db, ctx_b, limit=20)
        own_ids = {str(item.id) for item in own}
        leaked = [item for item in other if str(item.id) in own_ids]
    total += 1
    if record("other user cannot read private memory", len(leaked) == 0):
        passed += 1

    async with session_factory() as db:
        supplier_ctx = build_user_context(
            user_id=supplier_user.id,
            tenant_id=supplier_user.tenant_id,
            email=supplier_user.email,
            department=supplier_user.department,
            roles=["external_supplier"],
            supplier_id=supplier_user.supplier_id,
        )
        biz = await create_memory(
            db,
            ctx_a,
            MemoryWriteEvent(
                content="分析结论：SUP-002 风险升高因交付延迟",
                memory_type="supplier_risk_history",
                scope=MemoryScope.BUSINESS,
                supplier_id=supplier_user.supplier_id,
                is_analysis_conclusion=True,
            ),
        )
        await db.commit()
        supplier_memories = await list_user_memories(db, supplier_ctx, limit=20)
    total += 1
    if record(
        "external_supplier scoped memory",
        all(
            item.supplier_id is None or item.supplier_id == supplier_user.supplier_id
            for item in supplier_memories
        ),
    ):
        passed += 1

    allowed, _ = should_write_memory(MemoryWriteEvent(content="sk-dee2ba1335554f4d953e58adeedee9ba"))
    total += 1
    if record("reject api key memory", not allowed):
        passed += 1

    contract_block = "payment terms " + ("Net 60 clause " * 80)
    allowed2, _ = should_write_memory(MemoryWriteEvent(content=contract_block))
    total += 1
    if record("reject long contract memory", not allowed2):
        passed += 1

    async with httpx.AsyncClient() as client:
        token = await login(client, "procurement_manager@example.com")
        chat_session = f"chat-{uuid.uuid4().hex[:8]}"

        first = await chat(
            client,
            token,
            "请分析供应商 SUP-001 的供应链风险并给出简要结论。",
            session_id=chat_session,
        )
        total += 1
        if record("chat round1 analysis", first.get("status") == "completed", str(first.get("nodes_executed"))):
            passed += 1

        second = await chat(
            client,
            token,
            "上次那个供应商为什么风险高？",
            session_id=chat_session,
        )
        total += 1
        nodes = second.get("nodes_executed") or []
        answer = second.get("answer") or ""
        memory_used = second.get("memory_used") or []
        if record(
            "chat round2 uses memory context",
            "memory" in nodes and (len(memory_used) > 0 or "[memory:" in answer or "SUP-001" in answer),
            f"memory_used={len(memory_used)}",
        ):
            passed += 1

        total += 1
        if record(
            "review memory citation path",
            "[memory:" in answer or len(memory_used) > 0 or "历史记忆" in answer,
        ):
            passed += 1

        resp = await client.get(
            f"{API_BASE}/api/v1/memory/session/{chat_session}",
            headers={"Authorization": f"Bearer {token}"},
        )
        total += 1
        if record("memory session API", resp.status_code == 200 and len(resp.json().get("messages") or []) >= 2):
            passed += 1

    async with session_factory() as db:
        count = (await db.execute(select(Memory))).scalars().all()
    total += 1
    if record("business memory persisted", len(count) >= 1, f"rows={len(count)}"):
        passed += 1

    await clear_session(tenant_id, user_id, session_id)

    mvp3 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_test_mvp3.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    total += 1
    if record("mvp3 regression", mvp3.returncode == 0, mvp3.stdout.splitlines()[-1] if mvp3.stdout else ""):
        passed += 1
    else:
        print(mvp3.stdout)
        print(mvp3.stderr)

    graphrag = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_test_graphrag.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    total += 1
    if record("graphrag regression", graphrag.returncode == 0, graphrag.stdout.splitlines()[-1] if graphrag.stdout else ""):
        passed += 1
    else:
        print(graphrag.stdout)
        print(graphrag.stderr)

    print(f"\nMemory smoke: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
