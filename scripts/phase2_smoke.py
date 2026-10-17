#!/usr/bin/env python3
"""Check real map/tracking HTTP contracts through the frontend proxy."""

import json
import os
import time
import math
from pathlib import Path
from datetime import datetime, timezone
import httpx

ROOT = Path(__file__).resolve().parents[1]


def run():
    output = ROOT / ".local/acceptance/phase-2"
    output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        base_url="http://127.0.0.1:3100", trust_env=False, timeout=30
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": "enterprise@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        login.raise_for_status()
        payload = login.json()
        headers = {"Authorization": f"Bearer {payload['access_token']}"}
        for scenario, amount in [
            ("port-congestion", "3380000.00"),
            ("tier2-shutdown", "3860000.00"),
            ("regional-flood", "1780000.00"),
        ]:
            r = client.get(
                "/api/v1/business/network",
                params={"scenario_id": scenario},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            assert data["metrics"]["exposure_amount_cny"] == amount
            assert data["tenant_id"] == payload["user"]["tenant_id"]
            print("PASS scenario network and exposure", scenario)
        early = client.get(
            "/api/v1/business/network",
            params={"at_time": "2026-10-16T02:00:00+08:00"},
            headers=headers,
        ).json()
        assert (
            early["risk_events"] == []
            and early["metrics"]["exposure_amount_cny"] == "0.00"
        )
        for ship in early["shipments"]:
            assert ship["delay_hours"] == 0
            assert all(
                datetime.fromisoformat(p["at"])
                <= datetime.fromisoformat(early["as_of"])
                for p in ship["trace"]
            )
        print("PASS time clipping and ETA knowledge boundary")
        ships = client.get(
            "/api/v1/business/shipments",
            params={"mode": "ocean", "risk_only": True},
            headers=headers,
        ).json()["items"]
        assert len(ships) == 2
        for ship in ships:
            detail = client.get(
                "/api/v1/business/shipments/" + ship["id"], headers=headers
            )
            detail.raise_for_status()
            assert detail.json()["shipment"]["id"] == ship["id"]
        assert (
            client.get(
                "/api/v1/business/network", params={"mode": "space"}, headers=headers
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/v1/business/shipments/missing", headers=headers
            ).status_code
            == 404
        )
        assert client.get("/api/v1/business/network").status_code == 401
        print("PASS shipment detail, filters, invalid requests and authentication")
        for asset in [
            "/supply-chain",
            "/tracking",
            "/maps/land.geojson",
            "/maps/map-ui.woff2",
            "/maps/maplibre-gl-worker.mjs",
            "/map-sw.js",
        ]:
            assert client.get(asset).status_code == 200, asset
        print("PASS local map assets and application pages")
        durations = []
        for _ in range(20):
            started = time.perf_counter()
            response = client.get("/api/v1/business/network", headers=headers)
            response.raise_for_status()
            durations.append((time.perf_counter() - started) * 1000)
        timings = {
            "requests": len(durations),
            "concurrency": 1,
            "p50_ms": round(sorted(durations)[9], 2),
            "p95_ms": round(sorted(durations)[math.ceil(len(durations) * 0.95) - 1], 2),
            "scope": "localhost frontend proxy + authenticated network API, warm synthetic dataset",
        }
        print("PASS network API timing", timings)
    (output / "http-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "network_api": timings,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
