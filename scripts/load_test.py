#!/usr/bin/env python3
"""Simple HTTP load test for SupplyGuard API endpoints."""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PASSWORD = "password123"

ROLE_EMAILS = {
    "admin": "admin@example.com",
    "procurement_manager": "procurement_manager@example.com",
    "procurement_staff": "procurement_staff@example.com",
    "logistics_manager": "logistics_manager@example.com",
    "finance_manager": "finance_manager@example.com",
    "quality_manager": "quality_manager@example.com",
    "executive": "executive@example.com",
    "external_supplier": "supplier@example.com",
}

ENDPOINT_PAYLOADS = {
    "chat": (
        "POST",
        "/api/v1/chat",
        {"query": "Public Supply Policy 的主要内容是什么？", "top_k": 3, "use_memory": False},
    ),
    "rag": (
        "POST",
        "/api/v1/rag/query",
        {"query": "Public Supply Policy 的主要内容是什么？", "top_k": 3},
    ),
    "graphrag": (
        "POST",
        "/api/v1/graphrag/query",
        {"query": "SUP-001 交付延迟会影响哪些订单？", "query_type": "supplier_impact", "entity_code": "SUP-001"},
    ),
    "tools": (
        "POST",
        "/api/v1/tools/call",
        {"tool_name": "query_supplier_profile", "tool_input": {"supplier_code": "SUP-001"}},
    ),
}


@dataclass
class RequestResult:
    ok: bool
    latency_ms: float
    token_usage: dict = field(default_factory=dict)
    error: str | None = None


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((pct / 100) * (len(ordered) - 1)))
    return ordered[index]


async def login(client: httpx.AsyncClient, role: str) -> str:
    email = ROLE_EMAILS.get(role, ROLE_EMAILS["procurement_manager"])
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def run_one(
    client: httpx.AsyncClient,
    token: str,
    endpoint: str,
) -> RequestResult:
    method, path, payload = ENDPOINT_PAYLOADS[endpoint]
    started = time.perf_counter()
    try:
        response = await client.request(
            method,
            path,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        if response.status_code >= 400:
            return RequestResult(False, latency_ms, error=f"HTTP {response.status_code}")
        body = response.json()
        token_usage = body.get("token_usage") or {}
        return RequestResult(True, latency_ms, token_usage=token_usage)
    except Exception as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return RequestResult(False, latency_ms, error=str(exc))


async def run_load_test(
    *,
    endpoint: str,
    concurrency: int,
    requests_count: int,
    role: str,
) -> dict:
    if endpoint not in ENDPOINT_PAYLOADS:
        raise ValueError(f"Unknown endpoint: {endpoint}")

    async with httpx.AsyncClient(base_url=API_BASE, timeout=180.0) as client:
        token = await login(client, role)
        semaphore = asyncio.Semaphore(concurrency)
        results: list[RequestResult] = []

        async def worker() -> None:
            async with semaphore:
                results.append(await run_one(client, token, endpoint))

        started = time.perf_counter()
        await asyncio.gather(*[worker() for _ in range(requests_count)])
        elapsed = time.perf_counter() - started

    latencies = [item.latency_ms for item in results if item.ok]
    success_count = sum(1 for item in results if item.ok)
    failure_count = len(results) - success_count
    token_totals = [
        float(item.token_usage.get("total_tokens") or 0)
        for item in results
        if item.ok and item.token_usage
    ]
    cost_totals = [
        float(item.token_usage.get("estimated_cost") or 0)
        for item in results
        if item.ok and item.token_usage
    ]

    return {
        "endpoint": endpoint,
        "concurrency": concurrency,
        "total_requests": len(results),
        "success_count": success_count,
        "failure_count": failure_count,
        "failure_rate": round(failure_count / len(results), 4) if results else 0.0,
        "p50_latency_ms": round(percentile(latencies, 50), 2),
        "p95_latency_ms": round(percentile(latencies, 95), 2),
        "p99_latency_ms": round(percentile(latencies, 99), 2),
        "throughput_rps": round(len(results) / elapsed, 2) if elapsed > 0 else 0.0,
        "avg_token_usage": round(statistics.mean(token_totals), 2) if token_totals else 0.0,
        "avg_cost_estimate": round(statistics.mean(cost_totals), 8) if cost_totals else 0.0,
        "elapsed_seconds": round(elapsed, 2),
        "errors": [item.error for item in results if item.error][:5],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SupplyGuard API load test")
    parser.add_argument(
        "--endpoint",
        choices=["chat", "rag", "graphrag", "tools"],
        default="chat",
    )
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--role", default="procurement_manager", choices=list(ROLE_EMAILS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = asyncio.run(
        run_load_test(
            endpoint=args.endpoint,
            concurrency=args.concurrency,
            requests_count=args.requests,
            role=args.role,
        )
    )
    print("SupplyGuard load test report")
    print("=" * 40)
    for key, value in report.items():
        if key != "errors":
            print(f"{key}: {value}")
    if report.get("errors"):
        print(f"errors (sample): {report['errors']}")
    print("=" * 40)
    return 0 if report["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
