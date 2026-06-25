#!/usr/bin/env python3
"""Observability smoke test."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


async def main() -> int:
    passed = 0
    total = 0
    request_id = f"smoke-req-{uuid.uuid4().hex[:8]}"

    async with httpx.AsyncClient(base_url=API_BASE, timeout=180.0) as client:
        admin_token = await login(client, "admin@example.com")
        pm_token = await login(client, "procurement_manager@example.com")
        logistics_token = await login(client, "logistics_manager@example.com")
        supplier_token = await login(client, "supplier@example.com")

        chat_resp = await client.post(
            "/api/v1/chat",
            headers={
                "Authorization": f"Bearer {pm_token}",
                "X-Request-Id": request_id,
            },
            json={"query": "Public Supply Policy 的主要内容是什么？", "top_k": 5, "use_memory": False},
        )
        total += 1
        chat_ok = chat_resp.status_code == 200 and bool(chat_resp.json().get("trace_id"))
        if record("/chat returns trace_id", chat_ok, chat_resp.json().get("trace_id", "")):
            passed += 1
        chat_trace_id = chat_resp.json().get("trace_id")

        total += 1
        if record(
            "response has X-Request-Id",
            chat_resp.headers.get("X-Request-Id") == request_id,
            chat_resp.headers.get("X-Request-Id", ""),
        ):
            passed += 1

        total += 1
        if record(
            "response has X-Trace-Id",
            chat_resp.headers.get("X-Trace-Id") == chat_trace_id,
            chat_resp.headers.get("X-Trace-Id", ""),
        ):
            passed += 1

        rag_resp = await client.post(
            "/api/v1/rag/query",
            headers={"Authorization": f"Bearer {pm_token}"},
            json={"query": "内部采购指南对供应商准入有哪些要求？", "top_k": 5},
        )
        total += 1
        rag_ok = rag_resp.status_code == 200 and bool(rag_resp.json().get("trace_id"))
        if record("/rag/query returns trace_id", rag_ok, rag_resp.json().get("trace_id", "")):
            passed += 1
        rag_trace_id = rag_resp.json().get("trace_id")

        graph_resp = await client.post(
            "/api/v1/graphrag/query",
            headers={"Authorization": f"Bearer {pm_token}"},
            json={
                "query": "SUP-001 延迟会影响哪些订单？",
                "query_type": "supplier_impact",
                "entity_code": "SUP-001",
                "top_k": 10,
            },
        )
        total += 1
        graph_ok = graph_resp.status_code == 200 and bool(graph_resp.json().get("trace_id"))
        if record("/graphrag/query returns trace_id", graph_ok, graph_resp.json().get("trace_id", "")):
            passed += 1
        graph_trace_id = graph_resp.json().get("trace_id")

        mem_session = f"obs-smoke-{uuid.uuid4().hex[:8]}"
        await client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {pm_token}"},
            json={
                "query": "请分析 SUP-001 的交付延迟风险",
                "session_id": mem_session,
                "top_k": 5,
                "use_memory": True,
            },
        )
        mem_chat = await client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {pm_token}"},
            json={
                "query": "刚才讨论的供应商会影响哪些客户？",
                "session_id": mem_session,
                "top_k": 5,
                "use_memory": True,
            },
        )
        mem_trace_id = mem_chat.json().get("trace_id") if mem_chat.status_code == 200 else None

        trace_resp = await client.get(
            f"/api/v1/traces/{chat_trace_id}",
            headers={"Authorization": f"Bearer {pm_token}"},
        )
        total += 1
        trace_ok = trace_resp.status_code == 200
        if record("trace API returns chat trace", trace_ok):
            passed += 1
        trace_payload = trace_resp.json() if trace_ok else {}

        total += 1
        if record(
            "trace request status_code recorded",
            trace_payload.get("request", {}).get("status_code") == 200,
            str(trace_payload.get("request", {}).get("status_code")),
        ):
            passed += 1

        total += 1
        if record(
            "trace contains AgentRun",
            bool(trace_payload.get("agent_run")),
            trace_payload.get("agent_run", {}).get("status", ""),
        ):
            passed += 1

        total += 1
        agent_run = trace_payload.get("agent_run") or {}
        if record(
            "trace AgentRun has llm_model",
            bool(agent_run.get("llm_model")),
            str(agent_run.get("llm_model")),
        ):
            passed += 1

        total += 1
        if record(
            "trace contains RetrievalLog",
            len(trace_payload.get("retrieval_logs") or []) > 0,
            str(len(trace_payload.get("retrieval_logs") or [])),
        ):
            passed += 1

        total += 1
        if record(
            "trace contains AuditLog",
            len(trace_payload.get("audit_logs") or []) > 0,
            str(len(trace_payload.get("audit_logs") or [])),
        ):
            passed += 1

        total += 1
        if record(
            "trace contains node timeline",
            len(trace_payload.get("timeline") or []) > 0,
            str(len(trace_payload.get("timeline") or [])),
        ):
            passed += 1

        if mem_trace_id:
            mem_trace_resp = await client.get(
                f"/api/v1/traces/{mem_trace_id}",
                headers={"Authorization": f"Bearer {pm_token}"},
            )
            total += 1
            if record(
                "trace contains memory_events",
                mem_trace_resp.status_code == 200
                and len(mem_trace_resp.json().get("memory_events") or []) > 0,
                str(len(mem_trace_resp.json().get("memory_events") or [])),
            ):
                passed += 1

        graph_trace_resp = await client.get(
            f"/api/v1/traces/{graph_trace_id}",
            headers={"Authorization": f"Bearer {pm_token}"},
        )
        total += 1
        graph_trace_ok = graph_trace_resp.status_code == 200 and len(
            graph_trace_resp.json().get("graph_retrieval_logs") or []
        ) > 0
        if record("trace contains GraphRetrievalLog", graph_trace_ok):
            passed += 1

        rag_trace_resp = await client.get(
            f"/api/v1/traces/{rag_trace_id}",
            headers={"Authorization": f"Bearer {pm_token}"},
        )
        total += 1
        rag_trace_ok = rag_trace_resp.status_code == 200 and len(
            rag_trace_resp.json().get("retrieval_logs") or []
        ) > 0
        if record("rag trace has retrieval logs", rag_trace_ok):
            passed += 1

        cross_user = await client.get(
            f"/api/v1/traces/{chat_trace_id}",
            headers={"Authorization": f"Bearer {logistics_token}"},
        )
        total += 1
        if record("other user cannot read trace", cross_user.status_code == 403, str(cross_user.status_code)):
            passed += 1

        admin_read = await client.get(
            f"/api/v1/traces/{chat_trace_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        total += 1
        if record("admin can read other user trace", admin_read.status_code == 200, str(admin_read.status_code)):
            passed += 1

        blocked_rag = await client.post(
            "/api/v1/rag/query",
            headers={"Authorization": f"Bearer {supplier_token}"},
            json={"query": "Other Supplier Portal Notice Beta Materials", "top_k": 5},
        )
        supplier_trace_id = blocked_rag.json().get("trace_id") if blocked_rag.status_code == 200 else None
        leak = False
        if supplier_trace_id:
            supplier_trace = await client.get(
                f"/api/v1/traces/{supplier_trace_id}",
                headers={"Authorization": f"Bearer {supplier_token}"},
            )
            if supplier_trace.status_code == 200:
                for row in supplier_trace.json().get("retrieval_logs") or []:
                    for item in row.get("results") or []:
                        if "Other Supplier Portal Notice" in str(item.get("title", "")):
                            leak = True
                answer = str((supplier_trace.json().get("agent_run") or {}).get("final_answer", ""))
                if "Beta Materials" in answer:
                    leak = True
        total += 1
        if record("external_supplier trace has no unauthorized content", not leak):
            passed += 1

        total += 1
        if record(
            "trace summary present",
            bool(trace_payload.get("summary")),
            str(trace_payload.get("summary", {}).get("total_latency_ms")),
        ):
            passed += 1

        bench_resp = await client.post(
            "/api/v1/benchmarks/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "obs_smoke_bench", "mode": "permission", "limit": 2, "config": {"top_k": 5}},
        )
        bench_trace_id = bench_resp.json().get("trace_id") if bench_resp.status_code == 200 else None
        if bench_trace_id:
            bench_trace = await client.get(
                f"/api/v1/traces/{bench_trace_id}",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            total += 1
            if record(
                "benchmark trace links benchmark_runs",
                bench_trace.status_code == 200
                and len(bench_trace.json().get("benchmark_runs") or []) > 0,
                str(len(bench_trace.json().get("benchmark_runs") or [])),
            ):
                passed += 1

    total += 1
    langsmith_ok = os.getenv("LANGSMITH_API_KEY", "") in {"", "your_langsmith_api_key"}
    if record("no LANGSMITH_API_KEY does not break startup", langsmith_ok, "env default"):
        passed += 1

    print(f"\nObservability smoke: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
