#!/usr/bin/env python3
"""MVP-3 end-to-end smoke test."""

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

from packages.common.db.models.agent_run import AgentRun  # noqa: E402
from packages.common.db.models.audit_log import AuditLog  # noqa: E402
from packages.common.db.models.retrieval_log import RetrievalLog  # noqa: E402
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


async def rag_query(client: httpx.AsyncClient, token: str, query: str) -> dict:
    response = await client.post(
        f"{API_BASE}/api/v1/rag/query",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "top_k": 5},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()


async def chat(client: httpx.AsyncClient, token: str, query: str) -> dict:
    response = await client.post(
        f"{API_BASE}/api/v1/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"query": query, "top_k": 5},
        timeout=180.0,
    )
    response.raise_for_status()
    return response.json()


def has_evidence(result: dict) -> bool:
    return result.get("status") == "answered" and len(result.get("citations") or []) > 0


def no_evidence(result: dict) -> bool:
    answer = result.get("answer", "")
    return result.get("status") in {"no_evidence", "blocked"} or "未找到足够证据" in answer or "无权访问" in answer


def cites_title(result: dict, title: str) -> bool:
    return any(item.get("title") == title for item in (result.get("citations") or []))


def logistics_delay_report_ok(result: dict) -> bool:
    """Authorized logistics report retrieval — stable on citation, not LLM phrasing."""
    if not has_evidence(result):
        return False
    if cites_title(result, "Logistics Delay Analysis Report"):
        return True
    answer = result.get("answer", "").lower()
    return any(
        needle in answer
        for needle in ("port congestion", "港口", "拥堵", "shanghai", "上海", "delay", "延迟")
    )


def answer_contains(result: dict, *needles: str) -> bool:
    answer = result.get("answer", "")
    return any(needle in answer for needle in needles)


def blocked_confidential_contract(result: dict) -> bool:
    """Must not retrieve or leak confidential supplier contract terms."""
    if cites_title(result, "Confidential Supplier Framework Contract"):
        return False
    if answer_contains(result, "Net 60"):
        return False
    return True


def blocked_finance_pricing(result: dict) -> bool:
    """Must not retrieve or leak finance pricing terms."""
    if cites_title(result, "Finance Pricing Terms"):
        return False
    answer = result.get("answer", "")
    if "Volume discount tier 1: 3%" in answer:
        return False
    if "18%" in answer and "margin" in answer.lower():
        return False
    return True


def blocked_other_supplier_portal(result: dict) -> bool:
    """External supplier must not access another supplier's portal document."""
    for item in result.get("citations") or []:
        snippet = item.get("snippet", "")
        if "Beta Materials" in snippet and "2024-08-01" in snippet:
            return False
        if "SUP-002" in snippet:
            return False
    if answer_contains(result, "2024-08-01", "Component-B"):
        return False
    return True


async def count_logs() -> tuple[int, int, int]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        retrieval_count = (
            await session.execute(select(func.count()).select_from(RetrievalLog))
        ).scalar_one()
        agent_run_count = (
            await session.execute(select(func.count()).select_from(AgentRun))
        ).scalar_one()
        audit_count = (
            await session.execute(select(func.count()).select_from(AuditLog))
        ).scalar_one()
    return retrieval_count, agent_run_count, audit_count


async def main() -> int:
    print("SupplyGuard MVP-3 smoke test")
    print("=" * 60)
    results: list[bool] = []

    async with httpx.AsyncClient() as client:
        health = await client.get(f"{API_BASE}/health", timeout=10.0)
        results.append(record("API health", health.status_code == 200))

        tokens = {}
        for role_email in [
            "admin@example.com",
            "procurement_manager@example.com",
            "procurement_staff@example.com",
            "logistics_manager@example.com",
            "finance_manager@example.com",
            "supplier@example.com",
        ]:
            try:
                tokens[role_email] = await login(client, role_email)
                results.append(record(f"login {role_email}", True))
            except Exception as exc:
                results.append(record(f"login {role_email}", False, str(exc)))

        print("Running seed docs ingest...")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/ingest_seed_docs.py")],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        ingest_detail = ""
        if proc.stdout:
            ok_lines = [line for line in proc.stdout.splitlines() if line.startswith("[OK]")]
            ingest_detail = f"{len(ok_lines)} docs" if ok_lines else proc.stdout.strip()[-120:]
        if proc.returncode != 0 and proc.stderr:
            ingest_detail = proc.stderr.strip()[-200:]
        results.append(record("ingest seed docs", proc.returncode == 0, ingest_detail))

        contract_query = "Alpha Components 合同付款条款是什么？"
        pm_result = await rag_query(client, tokens["procurement_manager@example.com"], contract_query)
        results.append(
            record(
                "procurement_manager confidential contract",
                has_evidence(pm_result) and "Net 60" in pm_result.get("answer", ""),
                pm_result.get("status", ""),
            )
        )

        ps_result = await rag_query(client, tokens["procurement_staff@example.com"], contract_query)
        results.append(
            record(
                "procurement_staff confidential contract blocked",
                blocked_confidential_contract(ps_result),
                ps_result.get("status", ""),
            )
        )

        logistics_query = "最近物流延迟的主要原因是什么？"
        lm_ok = await rag_query(client, tokens["logistics_manager@example.com"], logistics_query)
        results.append(
            record(
                "logistics_manager logistics delay report",
                logistics_delay_report_ok(lm_ok),
                lm_ok.get("status", ""),
            )
        )

        finance_query = "财务定价条款中的 volume discount 是多少？"
        lm_fin = await rag_query(client, tokens["logistics_manager@example.com"], finance_query)
        results.append(
            record(
                "logistics_manager finance pricing blocked",
                blocked_finance_pricing(lm_fin),
                lm_fin.get("status", ""),
            )
        )

        portal_query = "Alpha Components 下一次交付数量和日期是什么？"
        sup_ok = await rag_query(client, tokens["supplier@example.com"], portal_query)
        results.append(
            record(
                "external_supplier own portal document",
                has_evidence(sup_ok),
                sup_ok.get("status", ""),
            )
        )

        other_sup_query = "Beta Materials 的下一次交付日期是什么？"
        sup_other = await rag_query(client, tokens["supplier@example.com"], other_sup_query)
        results.append(
            record(
                "external_supplier other supplier blocked",
                blocked_other_supplier_portal(sup_other),
                sup_other.get("status", ""),
            )
        )

        chat_result = await chat(
            client,
            tokens["procurement_manager@example.com"],
            "请总结 Alpha Components 合同中的付款条款。",
        )
        results.append(
            record(
                "/api/v1/chat response",
                bool(chat_result.get("answer"))
                and bool(chat_result.get("trace_id"))
                and bool(chat_result.get("agent_run_id")),
            )
        )

    retrieval_count, agent_run_count, audit_count = await count_logs()
    results.append(record("RetrievalLog has records", retrieval_count > 0, str(retrieval_count)))
    results.append(record("AgentRun has records", agent_run_count > 0, str(agent_run_count)))
    results.append(record("AuditLog has records", audit_count > 0, str(audit_count)))

    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Result: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
