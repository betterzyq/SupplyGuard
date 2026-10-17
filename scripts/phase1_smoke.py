#!/usr/bin/env python3
"""Real HTTP acceptance checks; does not invoke models or print credentials."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".local/acceptance/phase-1"
BASE = "http://127.0.0.1:3100"


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS {message}")


def run():
    with httpx.Client(base_url=BASE, timeout=30, trust_env=False) as client:
        check(client.get("/login").status_code == 200, "frontend login page")
        check(
            client.get("/api/v1/business/overview").status_code == 401,
            "unauthenticated business access denied",
        )
        for email, role in [
            ("enterprise@example.com", "enterprise"),
            ("admin@example.com", "admin"),
        ]:
            response = client.post(
                "/api/v1/auth/login",
                json={
                    "email": email,
                    "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
                },
            )
            check(
                response.status_code == 200,
                f"{role} login (existing passwords are not reset)",
            )
            payload = response.json()
            headers = {"Authorization": f"Bearer {payload['access_token']}"}
            check(
                payload["user"]["roles"] == [role],
                f"{role} has exactly one effective role",
            )
            permissions = client.get(
                "/api/v1/users/me/permissions", headers=headers
            ).json()
            check(
                permissions["can_upload_document"], f"{role} business upload permission"
            )
            check(
                permissions["can_run_benchmark"] is (role == "admin"),
                f"{role} benchmark permission",
            )
            expected = {
                "port-congestion": "3380000.00",
                "tier2-shutdown": "3860000.00",
                "regional-flood": "1780000.00",
            }
            for scenario, amount in expected.items():
                response = client.get(
                    "/api/v1/business/overview",
                    params={"scenario_id": scenario},
                    headers=headers,
                )
                check(response.status_code == 200, f"{role}: {scenario}")
                data = response.json()
                check(
                    data["metrics"]["exposure_amount_cny"] == amount,
                    f"{scenario} exposure reconciles",
                )
                check(
                    data["tenant_id"] == payload["user"]["tenant_id"],
                    "tenant context preserved",
                )
            check(
                client.get(
                    "/api/v1/business/overview?scenario_id=missing", headers=headers
                ).status_code
                == 404,
                "unknown scenario rejected",
            )
            check(
                client.get(
                    "/api/v1/admin/audit-logs?limit=1", headers=headers
                ).status_code
                == (200 if role == "admin" else 403),
                f"{role} admin API boundary",
            )
            if role == "enterprise":
                check(
                    client.get("/api/v1/benchmarks/runs", headers=headers).status_code
                    == 403,
                    "enterprise benchmark API denied",
                )
        # Existing internal account compatibility is optional if the original seed did not create one.
        legacy = client.post(
            "/api/v1/auth/login",
            json={
                "email": "procurement_manager@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        if legacy.status_code == 200:
            check(
                legacy.json()["user"]["roles"] == ["enterprise"],
                "legacy internal role normalized",
            )
        else:
            print(
                "SKIP legacy internal account login: not available with supplied demo password"
            )
        retired = client.post(
            "/api/v1/auth/login",
            json={
                "email": "supplier@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        check(retired.status_code in {401, 403}, "retired portal cannot log in")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "http-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "base": BASE,
            },
            indent=2,
        )
    )
    print("PASS: HTTP acceptance through frontend proxy")


if __name__ == "__main__":
    try:
        run()
    except (httpx.HTTPError, AssertionError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
