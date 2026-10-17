#!/usr/bin/env python3
"""Read a personal snapshot via authenticated HTTP without printing credentials."""

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / ".local/acceptance/phase-3"


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", help="64-character saved run/comparison id")
    parser.add_argument(
        "--latest", action="store_true", help="Verify latest HTTP smoke comparison"
    )
    parser.add_argument("--email", default="enterprise@example.com")
    args = parser.parse_args()
    expected = None
    if args.latest:
        latest = json.loads((OUTPUT / "http-smoke.json").read_text())
        identifier = latest["comparison_id"]
        expected = latest.get("snapshot_sha256")
    else:
        identifier = args.id
    if (
        not identifier
        or len(identifier) != 64
        or any(c not in "0123456789abcdef" for c in identifier)
    ):
        parser.error("provide --latest or --id with a valid SHA256 id")
    with httpx.Client(
        base_url="http://127.0.0.1:3100", trust_env=False, timeout=30
    ) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={
                "email": args.email,
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        login.raise_for_status()
        response = client.get(
            "/api/v1/simulation/runs/" + identifier,
            headers={"Authorization": "Bearer " + login.json()["access_token"]},
        )
        response.raise_for_status()
        result = response.json()
    actual = hashlib.sha256(
        json.dumps(
            result, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert not expected or actual == expected, "Persisted snapshot content changed"
    summary = {
        "status": "passed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": identifier,
        "snapshot_sha256": actual,
        "engine_version": result["engine_version"],
        "content_matches_previous_http": bool(expected),
        "api_pid": json.loads(
            (ROOT / ".local/acceptance/services/api.json").read_text()
        )["pid"],
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "snapshot-read.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        "PASS authenticated snapshot read; stored content unchanged"
        if expected
        else "PASS authenticated snapshot read"
    )
    print("Snapshot:", identifier)
    print("Engine:", result["engine_version"])


if __name__ == "__main__":
    run()
