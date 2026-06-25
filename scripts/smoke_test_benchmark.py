#!/usr/bin/env python3
"""Benchmark system smoke test."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.benchmarks.dataset import default_dataset_path, load_dataset  # noqa: E402
from packages.benchmarks.metrics import permission_violation_rate  # noqa: E402
from packages.common.db.models.benchmark import BenchmarkResult, BenchmarkRun  # noqa: E402
from packages.common.db.session import get_session_factory  # noqa: E402

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
PASSWORD = "password123"
DATASET = default_dataset_path()


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


def run_cli(mode: str, limit: int = 5) -> dict:
    proc = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "scripts/run_benchmark.py",
            "--mode",
            mode,
            "--limit",
            str(limit),
            "--name",
            f"smoke_{mode}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    text = proc.stdout
    if "__BENCHMARK_RESULT__" in text:
        payload = text.split("__BENCHMARK_RESULT__", 1)[1].strip()
        return json.loads(payload)
    start = text.find("{")
    if start < 0:
        raise ValueError(f"no JSON in benchmark output: {text[:200]}")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(text[start:])
    return obj


async def main() -> int:
    passed = 0
    total = 0
    session_factory = get_session_factory()

    total += 1
    if record("eval dataset exists", DATASET.exists(), str(DATASET)):
        passed += 1

    total += 1
    try:
        items = load_dataset(DATASET)
        ok = len(items) >= 100
        if record("eval dataset >= 100", ok, f"count={len(items)}"):
            passed += 1
    except Exception as exc:  # noqa: BLE001
        record("eval dataset >= 100", False, str(exc))

    for mode in ["secure_rag", "graphrag", "permission", "memory"]:
        total += 1
        try:
            result = await asyncio.to_thread(run_cli, mode, 5)
            ok = result.get("status") == "completed"
            if record(f"{mode} benchmark runs 5 items", ok, str(result.get("benchmark_run_id", ""))):
                passed += 1
        except Exception as exc:  # noqa: BLE001
            record(f"{mode} benchmark runs 5 items", False, str(exc))

    async with session_factory() as session:
        run_count = (await session.execute(select(func.count()).select_from(BenchmarkRun))).scalar_one()
        result_count = (await session.execute(select(func.count()).select_from(BenchmarkResult))).scalar_one()

    total += 1
    if record("benchmark_runs has records", run_count > 0, f"count={run_count}"):
        passed += 1

    total += 1
    if record("benchmark_results has records", result_count > 0, f"count={result_count}"):
        passed += 1

    reports_dir = ROOT / "data" / "eval" / "reports"
    latest_run = None
    async with session_factory() as session:
        latest_run = (
            await session.execute(select(BenchmarkRun).order_by(BenchmarkRun.started_at.desc()).limit(1))
        ).scalar_one_or_none()

    export_ok = False
    if latest_run:
        base = reports_dir / str(latest_run.id)
        export_ok = base.with_suffix(".md").exists() and base.with_suffix(".json").exists() and base.with_suffix(".csv").exists()
    total += 1
    if record("reports export md/json/csv", export_ok, str(latest_run.id if latest_run else "")):
        passed += 1

    perm_rows = [
        {"requires_permission": True, "should_be_blocked": True, "permission_violation": False},
        {"requires_permission": True, "should_be_blocked": True, "permission_violation": True},
    ]
    rate = permission_violation_rate(perm_rows)
    total += 1
    if record("permission_violation_rate computed", rate == 0.5, f"rate={rate}"):
        passed += 1

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120.0) as client:
        admin_token = await login(client, "admin@example.com")
        user_token = await login(client, "procurement_manager@example.com")

        total += 1
        admin_resp = await client.post(
            "/api/v1/benchmarks/run",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "smoke_api", "mode": "permission", "limit": 3, "config": {"top_k": 5}},
        )
        if record("benchmark API admin allowed", admin_resp.status_code == 200, str(admin_resp.status_code)):
            passed += 1

        total += 1
        user_resp = await client.post(
            "/api/v1/benchmarks/run",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"name": "smoke_api_denied", "mode": "permission", "limit": 3},
        )
        if record("benchmark API non-admin denied", user_resp.status_code == 403, str(user_resp.status_code)):
            passed += 1

    total += 1
    legacy = subprocess.run(["make", "smoke-mvp3"], cwd=ROOT, capture_output=True, text=True)
    legacy_ok = legacy.returncode == 0
    if record("legacy smoke-mvp3 still passes", legacy_ok, legacy.stdout.splitlines()[-1] if legacy.stdout else ""):
        passed += 1

    print(f"\nBenchmark smoke: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
