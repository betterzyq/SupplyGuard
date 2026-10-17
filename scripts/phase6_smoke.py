#!/usr/bin/env python3
"""Three real HTTP stories, durable tasks/reports, serial API timing; no external calls."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time
import uuid

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase1_check as limits  # noqa: E402
from acceptance_services import load_record, owns_process  # noqa: E402

ROOT = limits.ROOT
OUT = ROOT / ".local/acceptance/phase-6"


def percentile(values, q):
    return sorted(values)[max(0, int(len(values) * q + 0.999999) - 1)]


def own_rss(name):
    record = load_record(name)
    if not owns_process(name, record):
        raise RuntimeError("Acceptance process is not owned: " + name)
    fields = Path(f"/proc/{record['pid']}/status").read_text().splitlines()
    rss = next(int(x.split()[1]) for x in fields if x.startswith("VmRSS:"))
    ticks = Path(f"/proc/{record['pid']}/stat").read_text().rsplit(")", 1)[1].split()
    cpu_seconds = (int(ticks[11]) + int(ticks[12])) / os.sysconf("SC_CLK_TCK")
    return {
        "cpu_seconds": cpu_seconds,
        "pid": record["pid"],
        "birth": record["birth"],
        "rss_kib": rss,
        "scope": "verified parent process only; children/DB/browser excluded",
    }


def main():
    limits.constrain_cpu()
    OUT.mkdir(parents=True, exist_ok=True)
    checks, stories, timings = [], [], {}

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS", label, flush=True)

    with httpx.Client(
        base_url="http://127.0.0.1:3100/api/v1", timeout=45, trust_env=False
    ) as c:
        r = c.post(
            "/auth/login",
            json={
                "email": "enterprise@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        r.raise_for_status()
        login = r.json()
        h = {"Authorization": "Bearer " + login["access_token"]}

        def get(path, **kwargs):
            r = c.get(path, headers=h, **kwargs)
            r.raise_for_status()
            return r.json()

        def command(path, body, method="POST"):
            r = c.request(
                method,
                path,
                json=body,
                headers={**h, "Idempotency-Key": uuid.uuid4().hex},
            )
            r.raise_for_status()
            return r.json()

        for scenario in ("port-congestion", "tier2-shutdown", "regional-flood"):
            params = {"scenario_id": scenario}
            overview = get("/business/overview", params=params)
            network = get("/business/network", params=params)
            check(
                network["metrics"]["exposure_amount_cny"]
                == overview["metrics"]["exposure_amount_cny"],
                scenario + " overview/map amount matches",
            )
            template = get("/simulation/templates", params=params)
            options = template["default_option_ids"]
            plans = (
                [
                    {
                        "id": "plan-a",
                        "name": "P6验收备援",
                        "measures": [
                            {
                                "option_id": options[0],
                                "quantity": "1",
                                "duration_days": 1,
                            }
                        ],
                    }
                ]
                if options
                else []
            )
            comparison = command(
                "/simulation/comparison",
                {"simulation": {"scenario_id": scenario}, "plans": plans},
            )
            check(
                comparison["source_type"] == "synthetic",
                scenario + " comparison clearly synthetic",
            )
            capture = command(
                "/workspace/captures",
                {
                    "kind": "simulation",
                    "identifier": comparison["comparison_id"],
                    "share_with_tenant": True,
                },
            )
            check(
                capture["source_type"] == "synthetic",
                scenario + " explicit shared simulation provenance",
            )
            demo = command("/workspace/demo-scenario", params)
            task = command(
                "/workspace/tasks",
                {
                    "record_id": demo["events"][0]["id"],
                    "title": f"P6全链路验收（模拟）{scenario}-{uuid.uuid4().hex[:6]}",
                    "due_at": (
                        datetime.now(timezone.utc) + timedelta(days=2)
                    ).isoformat(),
                    "assignee_id": login["user"]["id"],
                    "measures": "仅记录模拟处置；方案快照 "
                    + comparison["comparison_id"],
                },
            )
            for action, extra in [
                ("start", {}),
                (
                    "submit",
                    {
                        "actual_cost_cny": "0.00",
                        "result": "模拟执行记录，不代表真实节省",
                    },
                ),
                ("complete", {"result": "流程验收复核，交付改善需另行核实"}),
            ]:
                task = command(
                    "/workspace/tasks/" + task["id"],
                    {"expected_version": task["version"], "action": action, **extra},
                    "PATCH",
                )
            check(
                task["state"] == "completed"
                and get("/workspace/tasks/" + task["id"] + "/history")["total"] == 4,
                scenario + " complete durable lifecycle and audit",
            )
            report = command("/workspace/reports", {"kind": "risk", "format": "xlsx"})
            r = c.get("/workspace/reports/" + report["id"] + "/download", headers=h)
            check(
                r.status_code == 200
                and hashlib.sha256(r.content).hexdigest() == report["sha256"],
                scenario + " actual export hash verified",
            )
            stories.append(
                {
                    "scenario": scenario,
                    "task_id": task["id"],
                    "comparison_id": comparison["comparison_id"],
                    "report_id": report["id"],
                    "report_sha256": report["sha256"],
                    "metrics": overview["metrics"],
                    "sites": len(network["sites"]),
                    "shipments": len(network["shipments"]),
                }
            )
        resource_before = {name: own_rss(name) for name in ("api", "web")}
        resource_started = time.perf_counter()
        for path in (
            "/business/overview",
            "/business/network",
            "/simulation/templates",
            "/prediction/report",
            "/workspace/records?limit=20",
        ):
            samples, failed = [], 0
            for i in range(21):
                started = time.perf_counter()
                r = c.get(path, headers=h)
                elapsed = (time.perf_counter() - started) * 1000
                if i == 0:
                    first = elapsed
                    r.raise_for_status()
                    continue
                samples.append(round(elapsed, 3))
                failed += int(r.status_code != 200)
            timings[path] = {
                "warmup_ms": round(first, 3),
                "samples_ms": samples,
                "n": len(samples),
                "concurrency": 1,
                "p50_ms": round(statistics.median(samples), 3),
                "p95_ms": percentile(samples, 0.95),
                "errors": failed,
                "error_rate": failed / len(samples),
            }
            check(failed == 0, "serial API performance no errors " + path)
        check(
            c.get("/workspace/reports").status_code == 401, "anonymous exports denied"
        )
        check(
            c.get("/benchmarks/runs", headers=h).status_code == 403,
            "enterprise developer API denied",
        )
    resource_elapsed = time.perf_counter() - resource_started
    resources = {name: own_rss(name) for name in ("api", "web")}
    for name, sample in resources.items():
        sample["sampling_seconds"] = round(resource_elapsed, 3)
        sample["cpu_percent_one_core"] = round(
            (sample["cpu_seconds"] - resource_before[name]["cpu_seconds"])
            / resource_elapsed
            * 100,
            2,
        )
    result = {
        "status": "passed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "stories": stories,
        "api_timings": timings,
        "equipment": {
            "architecture": platform.machine(),
            "python": platform.python_version(),
            "client_cpu_affinity": sorted(os.sched_getaffinity(0)),
            "cpu_model": next(
                (
                    s.split(":", 1)[1].strip()
                    for s in Path("/proc/cpuinfo").read_text().splitlines()
                    if s.startswith("model name")
                ),
                "unknown",
            ),
            "browser_mode": "SwiftShader CPU only; browser performance reported separately",
        },
        "resource_samples": resources,
        "scope": "Loopback Next proxy; fixed read endpoints; 20 serial warm samples; not concurrency capacity or SLA",
    }
    (OUT / "http-smoke.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
