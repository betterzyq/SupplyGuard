#!/usr/bin/env python3
"""Real HTTP verification of P3 arithmetic, snapshots and constrained measures."""

import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def run():
    checks = []

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS", label, flush=True)

    with httpx.Client(
        base_url="http://127.0.0.1:3100", trust_env=False, timeout=30
    ) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "enterprise@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        response.raise_for_status()
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        endpoint = "/api/v1/simulation"
        template = client.get(
            endpoint + "/templates", params={"preset_id": "hand-check"}, headers=headers
        )
        template.raise_for_status()
        check(
            template.json()["config"]["materials"][0]["initial_stock"] == "100",
            "hand fixture and authenticated template",
        )

        def body(duration):
            return {
                "preset_id": "hand-check",
                "event_overrides": [
                    {"event_id": e, "duration_days": duration}
                    for e in ["EVT-PORT", "EVT-PORT-SECONDARY"]
                ],
            }

        request = body(3)
        response = client.post(endpoint + "/run", json=request, headers=headers)
        response.raise_for_status()
        check(
            response.json()["result"]["metrics"]["delayed_orders"] == 0
            and response.json()["result"]["materials"][0]["peak_shortage_units"] == "0",
            "100/20 stock, three-day disruption: no shortage",
        )
        request = body(7)
        started = time.perf_counter()
        response = client.post(
            endpoint + "/comparison",
            headers=headers,
            json={
                "simulation": request,
                "plans": [
                    {
                        "id": "a",
                        "name": "替代采购",
                        "measures": [
                            {
                                "option_id": "alternative-MAT-01",
                                "quantity": 20,
                                "duration_days": 7,
                            }
                        ],
                    },
                    {
                        "id": "b",
                        "name": "库存调拨",
                        "measures": [
                            {
                                "option_id": "transfer-MAT-01",
                                "quantity": 80,
                                "duration_days": 1,
                            }
                        ],
                    },
                ],
            },
        )
        response.raise_for_status()
        comparison = response.json()
        elapsed = round((time.perf_counter() - started) * 1000, 2)
        baseline = comparison["baseline"]["result"]
        check(
            baseline["metrics"]["first_shortage_day"] == 5
            and baseline["materials"][0]["peak_shortage_units"] == "40",
            "seven-day disruption: D6 first shortage, peak 40",
        )
        check(
            [
                p["run"]["result"]["metrics"]["delayed_orders"]
                for p in comparison["plans"]
            ]
            == [0, 0],
            "both feasible measures remove hand-case delay",
        )
        check(
            [p["delta"]["incremental_cost_cny"] for p in comparison["plans"]]
            == ["4500.00", "1140.00"],
            "incremental costs 4500 and 1140, not fictional savings",
        )
        saved = client.get(
            endpoint + "/runs/" + comparison["comparison_id"], headers=headers
        )
        saved.raise_for_status()
        check(saved.json() == comparison, "saved comparison can be read identically")
        repeated = client.post(endpoint + "/run", headers=headers, json=request)
        repeated.raise_for_status()
        check(
            repeated.json()["run_id"] == comparison["baseline"]["run_id"],
            "same input produces same run hash",
        )
        invalid = client.post(
            endpoint + "/run",
            headers=headers,
            json={
                **request,
                "measures": [
                    {"option_id": "alternative-MAT-01-uncertified", "quantity": 10}
                ],
            },
        )
        check(invalid.status_code == 422, "uncertified measure rejected")
        check(
            client.post(endpoint + "/run", json=request).status_code == 401,
            "unauthenticated simulation rejected",
        )
        for scenario in ["port-congestion", "tier2-shutdown", "regional-flood"]:
            data = client.post(
                endpoint + "/run", headers=headers, json={"scenario_id": scenario}
            )
            data.raise_for_status()
            check(
                data.json()["input_snapshot"]["config"]["scenario_id"] == scenario,
                "manufacturing scenario " + scenario,
            )
    output = ROOT / ".local/acceptance/phase-3"
    output.mkdir(parents=True, exist_ok=True)
    (output / "http-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
                "hand_comparison_ms": elapsed,
                "comparison_id": comparison["comparison_id"],
                "snapshot_sha256": hashlib.sha256(
                    json.dumps(
                        comparison,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                ).hexdigest(),
                "api_pid": json.loads(
                    (ROOT / ".local/acceptance/services/api.json").read_text()
                )["pid"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    )


if __name__ == "__main__":
    run()
