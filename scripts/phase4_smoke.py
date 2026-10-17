#!/usr/bin/env python3
"""Real HTTP auth, model scoring, domain rejection and public evidence download."""

import hashlib
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import httpx

ROOT = Path(__file__).resolve().parents[1]


def run():
    checks = []

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS", label, flush=True)

    with httpx.Client(
        base_url="http://127.0.0.1:3100", trust_env=False, timeout=45
    ) as c:
        check(c.get("/api/v1/prediction/report").status_code == 401, "anonymous denied")
        for role in ["enterprise", "admin"]:
            login = c.post(
                "/api/v1/auth/login",
                json={
                    "email": role + "@example.com",
                    "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
                },
            )
            login.raise_for_status()
            headers = {"Authorization": "Bearer " + login.json()["access_token"]}
            report = c.get("/api/v1/prediction/report", headers=headers)
            report.raise_for_status()
            r = report.json()
            check(
                r["tenant_id"] == login.json()["user"]["tenant_id"]
                and r["domain"] == "dataco-retail-historical",
                role + " report bound to authenticated tenant",
            )
            items = c.get("/api/v1/prediction/cases", headers=headers)
            items.raise_for_status()
            sample = items.json()["items"][0]
            p = c.post(
                "/api/v1/prediction/predict",
                headers=headers,
                json={"case_id": sample["case_id"]},
            )
            p.raise_for_status()
            check(
                abs(p.json()["probability"] - sample["probability"]) < 1e-12
                and p.json()["model_version"] == r["model_version"],
                role + " trained inference matches locked test result",
            )
            invalid = c.post(
                "/api/v1/prediction/predict",
                headers=headers,
                json={"case_id": "SG-2026-0001", "domain": "manufacturing"},
            )
            check(invalid.status_code == 422, "manufacturing transfer rejected " + role)
            check(
                c.get(
                    "/api/v1/prediction/artifacts/model.joblib", headers=headers
                ).status_code
                == 404,
                "private model download rejected " + role,
            )
            downloaded = c.get(
                "/api/v1/prediction/artifacts/report.json", headers=headers
            )
            downloaded.raise_for_status()
            local = json.loads((ROOT / ".local/prediction/active.json").read_text())
            check(
                hashlib.sha256(downloaded.content).hexdigest()
                == local["report_sha256"],
                "download artifact matches active SHA256 " + role,
            )
            contracts = c.get(
                "/api/v1/prediction/evaluation-contracts", headers=headers
            )
            check(
                contracts.status_code == (200 if role == "admin" else 403),
                "admin-only evaluation contracts " + role,
            )
            if role == "admin":
                check(
                    contracts.json()["status"] == "passed"
                    and contracts.json()["live_retrieval_status"] == "not_run",
                    "offline and live quality clearly separated",
                )
                legacy = c.post(
                    "/api/v1/benchmarks/run",
                    headers=headers,
                    json={"name": "must-not-run", "mode": "secure_rag"},
                )
                check(legacy.status_code == 409, "obsolete live role gold cannot run")
        for name in ["precision-recall.png", "calibration.png"]:
            image = c.get("/api/v1/prediction/artifacts/" + name, headers=headers)
            check(
                image.status_code == 200 and image.content.startswith(b"\x89PNG"),
                "scientific plot " + name,
            )
    output = ROOT / ".local/acceptance/phase-4"
    output.mkdir(parents=True, exist_ok=True)
    (output / "http-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
                "run_id": r["run_id"],
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    run()
