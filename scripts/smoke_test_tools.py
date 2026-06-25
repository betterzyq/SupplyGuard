#!/usr/bin/env python3
"""MCP tools smoke test."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PASSWORD = "password123"

ALL_TOOLS = [
    "query_supplier_profile",
    "query_supplier_risk_events",
    "query_supplier_delivery_history",
    "query_supplier_contract_summary",
    "query_delivery_status",
    "query_delay_events",
    "query_route_info",
    "export_risk_report",
    "export_benchmark_results",
]


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


async def call_tool(
    client: httpx.AsyncClient,
    token: str,
    tool_name: str,
    tool_input: dict | None = None,
) -> dict:
    response = await client.post(
        "/api/v1/tools/call",
        headers={"Authorization": f"Bearer {token}"},
        json={"tool_name": tool_name, "tool_input": tool_input or {}},
    )
    response.raise_for_status()
    return response.json()


async def main() -> int:
    passed = 0
    total = 0

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        admin_token = await login(client, "admin@example.com")
        pm_token = await login(client, "procurement_manager@example.com")
        staff_token = await login(client, "procurement_staff@example.com")
        logistics_token = await login(client, "logistics_manager@example.com")
        finance_token = await login(client, "finance_manager@example.com")
        supplier_token = await login(client, "supplier@example.com")

        admin_results = []
        for tool_name in ALL_TOOLS:
            payload = {"supplier_code": "SUP-001"} if tool_name.startswith("query_supplier") else {}
            if tool_name == "query_delivery_status":
                payload = {"supplier_code": "SUP-001"}
            result = await call_tool(client, admin_token, tool_name, payload)
            admin_results.append(result)
        total += 1
        admin_ok = all(r["status"] in {"success", "approval_required"} for r in admin_results)
        if record("admin can call all tools", admin_ok, f"{len(admin_results)} tools"):
            passed += 1

        total += 1
        pm_contract = await call_tool(
            client, pm_token, "query_supplier_contract_summary", {"supplier_code": "SUP-001"}
        )
        if record(
            "procurement_manager can query_supplier_contract_summary",
            pm_contract["status"] == "success",
            pm_contract["status"],
        ):
            passed += 1

        total += 1
        staff_contract = await call_tool(
            client, staff_token, "query_supplier_contract_summary", {"supplier_code": "SUP-001"}
        )
        if record(
            "procurement_staff cannot query_supplier_contract_summary",
            staff_contract["status"] == "denied",
            staff_contract["status"],
        ):
            passed += 1

        total += 1
        logistics_status = await call_tool(
            client, logistics_token, "query_delivery_status", {"supplier_code": "SUP-001"}
        )
        if record(
            "logistics_manager can query_delivery_status",
            logistics_status["status"] == "success",
            logistics_status["status"],
        ):
            passed += 1

        total += 1
        finance_route = await call_tool(
            client, finance_token, "query_route_info", {"origin": "Shanghai", "destination": "Shenzhen"}
        )
        if record(
            "finance_manager cannot query_route_info",
            finance_route["status"] == "denied",
            finance_route["status"],
        ):
            passed += 1

        total += 1
        supplier_other = await call_tool(
            client, supplier_token, "query_supplier_profile", {"supplier_code": "SUP-002"}
        )
        if record(
            "external_supplier cannot query other supplier",
            supplier_other["status"] == "denied",
            supplier_other["status"],
        ):
            passed += 1

        total += 1
        export_result = await call_tool(client, pm_token, "export_risk_report", {})
        if record(
            "export_risk_report returns approval_required",
            export_result["status"] == "approval_required",
            export_result["status"],
        ):
            passed += 1

        total += 1
        log_check = await call_tool(
            client, pm_token, "query_supplier_profile", {"supplier_code": "SUP-001"}
        )
        trace_id = log_check["trace_id"]
        tool_call_id = log_check.get("tool_call_id")
        log_ok = log_check["status"] == "success" and bool(tool_call_id)
        if record("ToolCallLog written via API", log_ok, tool_call_id or ""):
            passed += 1

        total += 1
        chat_resp = await client.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {pm_token}"},
            json={
                "query": "请查询供应商档案 SUP-001 的基本信息",
                "top_k": 3,
                "use_memory": False,
            },
        )
        chat_ok = chat_resp.status_code == 200
        chat_body = chat_resp.json()
        chat_trace = chat_body.get("trace_id", "")
        nodes = chat_body.get("nodes_executed") or []
        chat_tool_ok = chat_ok and "tool" in nodes and chat_body.get("route_mode") == "tool"
        if record(
            "/api/v1/chat triggers Tool Node",
            chat_tool_ok,
            f"nodes={nodes}, route={chat_body.get('route_mode')}",
        ):
            passed += 1

        total += 1
        trace_resp = await client.get(
            f"/api/v1/traces/{chat_trace or trace_id}",
            headers={"Authorization": f"Bearer {pm_token}"},
        )
        trace_ok = trace_resp.status_code == 200
        trace_body = trace_resp.json() if trace_ok else {}
        tool_calls = trace_body.get("tool_calls") or []
        timeline_tools = [item for item in (trace_body.get("timeline") or []) if item.get("type") == "tool"]
        trace_tool_ok = trace_ok and (len(tool_calls) > 0 or len(timeline_tools) > 0)
        if record(
            "trace API shows tool call",
            trace_tool_ok,
            f"tool_calls={len(tool_calls)}, timeline_tools={len(timeline_tools)}",
        ):
            passed += 1

        total += 1
        tools_list = await client.get(
            "/api/v1/tools",
            headers={"Authorization": f"Bearer {staff_token}"},
        )
        staff_tools = {item["name"] for item in tools_list.json().get("tools", [])}
        list_ok = "query_supplier_profile" in staff_tools and "query_supplier_contract_summary" not in staff_tools
        if record("GET /api/v1/tools respects role whitelist", list_ok, str(sorted(staff_tools))):
            passed += 1

        total += 1
        own_profile = await call_tool(
            client, supplier_token, "query_supplier_profile", {"supplier_code": "SUP-001"}
        )
        if record(
            "external_supplier can query own supplier profile",
            own_profile["status"] == "success",
            own_profile["status"],
        ):
            passed += 1

    print(f"\nResult: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
