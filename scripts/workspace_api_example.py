#!/usr/bin/env python3
"""Local enterprise API example; no token logging or external message delivery."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import uuid
import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--kind", choices=["site", "order", "shipment", "event"], default="site"
    )
    p.add_argument("--file", type=Path, default=ROOT / "data/examples/phase5/site.csv")
    p.add_argument(
        "--confirm",
        action="store_true",
        help="Explicitly confirm a clean preview into this tenant",
    )
    a = p.parse_args()
    path = a.file.resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise SystemExit("Example reads only a chosen file inside SupplyGuard")
    with httpx.Client(
        base_url="http://127.0.0.1:3100", trust_env=False, timeout=45
    ) as c:
        response = c.post(
            "/api/v1/auth/login",
            json={
                "email": "enterprise@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        response.raise_for_status()
        auth = {"Authorization": "Bearer " + response.json()["access_token"]}
        schema = c.get("/api/v1/workspace/schema", headers=auth)
        schema.raise_for_status()
        fields = schema.json()["fields"][a.kind]
        content = path.read_bytes()
        key = "example-" + uuid.uuid4().hex
        preview = c.post(
            "/api/v1/workspace/imports/preview",
            headers={**auth, "Idempotency-Key": key},
            data={
                "kind": a.kind,
                "source_type": "synthetic",
                "mapping": json.dumps({f: f for f in fields}),
            },
            files={"file": (path.name, content)},
        )
        preview.raise_for_status()
        batch = preview.json()
        print(
            json.dumps(
                {
                    "batch_id": batch["id"],
                    "state": batch["state"],
                    "errors": batch["errors"],
                    "file_sha256": hashlib.sha256(content).hexdigest(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        if a.confirm:
            if batch["errors"]:
                raise SystemExit("No confirm: preview has errors")
            committed = c.post(
                "/api/v1/workspace/imports/" + batch["id"] + "/confirm",
                headers={**auth, "Idempotency-Key": "confirm-" + batch["id"]},
                json={},
            )
            committed.raise_for_status()
            print(json.dumps(committed.json(), ensure_ascii=False))


if __name__ == "__main__":
    main()
