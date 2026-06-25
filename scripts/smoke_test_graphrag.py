#!/usr/bin/env python3
"""GraphRAG smoke test."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.common.db.models.graph_retrieval_log import GraphRetrievalLog  # noqa: E402
from packages.common.graph.neo4j_client import check_neo4j_health  # noqa: E402
from packages.common.db.session import get_session_factory  # noqa: E402

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


async def graph_query(
    client: httpx.AsyncClient,
    token: str,
    *,
    query: str,
    query_type: str,
    entity_code: str | None = None,
) -> httpx.Response:
    return await client.post(
        f"{API_BASE}/api/v1/graphrag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": query,
            "query_type": query_type,
            "entity_code": entity_code,
            "top_k": 20,
        },
        timeout=120.0,
    )


async def chat(client: httpx.AsyncClient, token: str, query: str) -> dict:
    response = await client.post(
        f"{API_BASE}/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "top_k": 5},
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()


async def main() -> int:
    passed = 0
    total = 0

    health = await check_neo4j_health()
    total += 1
    if record("neo4j connectivity", health.get("status") == "ok", str(health)):
        passed += 1

    build = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_supply_graph.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    total += 1
    if record("build_supply_graph", build.returncode == 0, build.stderr.strip() or build.stdout.strip()[-120:]):
        passed += 1
    else:
        print(build.stdout)
        print(build.stderr)

    async with httpx.AsyncClient() as client:
        admin_token = await login(client, "admin@example.com")
        procurement_token = await login(client, "procurement_manager@example.com")
        logistics_token = await login(client, "logistics_manager@example.com")
        supplier_token = await login(client, "supplier@example.com")

        resp = await graph_query(
            client,
            procurement_token,
            query="供应商 SUP-001 延迟会影响哪些产品、订单和客户？",
            query_type="supplier_impact",
            entity_code="SUP-001",
        )
        total += 1
        if resp.status_code == 200 and len(resp.json().get("graph_paths") or []) > 0:
            passed += 1
            record("supplier_impact paths", True, f"paths={len(resp.json()['graph_paths'])}")
        else:
            record("supplier_impact paths", False, resp.text[:200])

        resp = await graph_query(
            client,
            procurement_token,
            query="产品 P001 依赖哪些供应商和物料？",
            query_type="product_dependency",
            entity_code="P001",
        )
        total += 1
        if resp.status_code == 200 and len(resp.json().get("graph_paths") or []) > 0:
            passed += 1
            record("product_dependency paths", True)
        else:
            record("product_dependency paths", False, resp.text[:200])

        resp = await graph_query(
            client,
            procurement_token,
            query="SUP-001 有哪些替代供应商？",
            query_type="supplier_alternatives",
            entity_code="SUP-001",
        )
        total += 1
        if resp.status_code == 200 and len(resp.json().get("graph_paths") or []) > 0:
            passed += 1
            record("supplier_alternatives", True)
        else:
            record("supplier_alternatives", False, resp.text[:200])

        own = await graph_query(
            client,
            supplier_token,
            query="SUP-001 影响哪些订单？",
            query_type="supplier_impact",
            entity_code="SUP-001",
        )
        foreign = await graph_query(
            client,
            supplier_token,
            query="SUP-002 影响哪些订单？",
            query_type="supplier_impact",
            entity_code="SUP-002",
        )
        total += 1
        if own.status_code == 200 and foreign.status_code == 403:
            passed += 1
            record("external_supplier scope", True)
        else:
            record("external_supplier scope", False, f"own={own.status_code}, foreign={foreign.status_code}")

        resp = await graph_query(
            client,
            procurement_token,
            query="SUP-001 supplier impact",
            query_type="supplier_impact",
            entity_code="SUP-001",
        )
        total += 1
        if resp.status_code == 200:
            passed += 1
            record("procurement_manager supplier_impact", True)
        else:
            record("procurement_manager supplier_impact", False, resp.text[:120])

        resp = await graph_query(
            client,
            logistics_token,
            query="最近交付延迟影响",
            query_type="delivery_delay_impact",
        )
        total += 1
        if resp.status_code == 200:
            passed += 1
            record("logistics_manager delivery_delay_impact", True)
        else:
            record("logistics_manager delivery_delay_impact", False, resp.text[:120])

        chat_graph = await chat(
            client,
            procurement_token,
            "供应商 SUP-001 延迟会影响哪些产品和订单？",
        )
        total += 1
        nodes = chat_graph.get("nodes_executed") or []
        answer = chat_graph.get("answer") or ""
        if "graphrag" in nodes and ("[graph:" in answer or "graph_path" in answer):
            passed += 1
            record("chat routes to graphrag", True, str(nodes))
        else:
            record("chat routes to graphrag", False, str(nodes))

        chat_hybrid = await chat(
            client,
            procurement_token,
            "供应商 SUP-001 延迟会影响哪些订单？请结合合同付款条款说明风险。",
        )
        total += 1
        answer = chat_hybrid.get("answer") or ""
        has_graph = "[graph:" in answer or "graph_path" in answer
        has_doc = len(chat_hybrid.get("citations") or []) > 0 or "[doc:" in answer
        if has_graph and has_doc:
            passed += 1
            record("hybrid graph + citation", True)
        else:
            record("hybrid graph + citation", False, f"graph={has_graph}, doc={has_doc}")

    session_factory = get_session_factory()
    async with session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(GraphRetrievalLog))).scalar_one()
    total += 1
    if record("GraphRetrievalLog written", count > 0, f"count={count}"):
        passed += 1

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

    print(f"\nGraphRAG smoke: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
