#!/usr/bin/env python3
"""Real HTTP persistence, import, lifecycle, report and local event verification."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import uuid
import httpx
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / ".local/acceptance/phase-5"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--verify-saved", action="store_true")
    args = p.parse_args()
    checks = []
    service_file = ROOT / ".local/acceptance/services/api.json"
    service = json.loads(service_file.read_text())

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS", label, flush=True)

    with httpx.Client(
        base_url="http://127.0.0.1:3100", timeout=45, trust_env=False
    ) as c:
        r = c.post(
            "/api/v1/auth/login",
            json={
                "email": "enterprise@example.com",
                "password": os.getenv("SUPPLYGUARD_DEMO_PASSWORD", "password123"),
            },
        )
        r.raise_for_status()
        h = {"Authorization": "Bearer " + r.json()["access_token"]}
        user = r.json()["user"]
        base = "/api/v1/workspace"

        def command(path, body, key=None, method="POST"):
            r = c.request(
                method,
                base + path,
                headers={**h, "Idempotency-Key": key or uuid.uuid4().hex},
                json=body,
            )
            r.raise_for_status()
            return r.json()

        if args.verify_saved:
            saved = json.loads((OUT / "http-smoke.json").read_text())
            before = saved.get("api_process")
            if before:
                check(
                    before != {"pid": service["pid"], "birth": service["birth"]},
                    "API process identity changed after saved smoke",
                )
            for resource, identifier in [
                ("tasks", saved["task_id"]),
                ("records", saved["record_id"]),
            ]:
                r = c.get(base + "/" + resource + "/" + identifier, headers=h)
                check(r.status_code == 200, "persisted after restart " + resource)
            check(
                c.get(base + "/tasks/" + saved["task_id"], headers=h).json()["state"]
                == "completed",
                "completed state survives process restart",
            )
            check(
                c.get(
                    base + "/reports/" + saved["report_id"] + "/download", headers=h
                ).status_code
                == 200,
                "report bytes survive process restart",
            )
            (OUT / "restart-verification.json").write_text(
                json.dumps(
                    {
                        "status": "passed",
                        "checks": checks,
                        "task_id": saved["task_id"],
                        "before_api": before,
                        "after_api": {"pid": service["pid"], "birth": service["birth"]},
                    },
                    indent=2,
                )
                + "\n"
            )
            return
        check(c.get(base + "/records").status_code == 401, "anonymous workspace denied")
        demo = command("/demo-scenario", {"scenario_id": "port-congestion"})
        record_id = demo["events"][0]["id"]
        stamp = uuid.uuid4().hex[:8]
        code = "QA-P5-" + stamp
        data = f"code,name,site_type,latitude,longitude,country\n{code},P5验收站点,factory,22.55,114.06,CN\n".encode()
        key = uuid.uuid4().hex
        r = c.post(
            base + "/imports/preview",
            headers={**h, "Idempotency-Key": key},
            data={
                "kind": "site",
                "source_type": "synthetic",
                "mapping": json.dumps(
                    {
                        x: x
                        for x in [
                            "code",
                            "name",
                            "site_type",
                            "latitude",
                            "longitude",
                            "country",
                        ]
                    }
                ),
            },
            files={"file": ("phase5-smoke.csv", data)},
        )
        r.raise_for_status()
        batch = r.json()
        check(
            batch["state"] == "validated" and not batch["errors"],
            "valid file preview without writes",
        )
        for bad_mapping, bad_name, bad_content, expected in [
            ('{"code":[]}', "malformed-map.csv", data, "invalid_mapping"),
            (
                json.dumps({"code": "code"}),
                "malformed.xlsx",
                b"not a zip",
                "invalid_file",
            ),
        ]:
            rejected = c.post(
                base + "/imports/preview",
                headers={**h, "Idempotency-Key": uuid.uuid4().hex},
                data={
                    "kind": "site",
                    "source_type": "synthetic",
                    "mapping": bad_mapping,
                },
                files={"file": (bad_name, bad_content)},
            )
            check(
                rejected.status_code == 422
                and rejected.json()["error"]["code"] == expected,
                "deployed parser rejects " + expected,
            )
        confirmed = command("/imports/" + batch["id"] + "/confirm", {})
        check(confirmed["inserted"] == 1, "atomic confirmation writes one site")
        repeated = command("/imports/" + batch["id"] + "/confirm", {})
        check(repeated["replayed"], "repeated confirmation does not duplicate records")
        check(
            c.get(
                base + "/records", params={"kind": "site", "q": code}, headers=h
            ).json()["total"]
            == 1,
            "same tenant readback and filter",
        )
        task = command(
            "/tasks",
            {
                "record_id": record_id,
                "title": "P5验收任务（模拟）" + stamp,
                "assignee_id": user["id"],
                "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
                "measures": "仅记录验收流程，不实际执行采购或通知",
            },
        )
        task_id = task["id"]
        for action, details in [
            ("start", {}),
            (
                "submit",
                {
                    "result": "验收措施记录已填写，待人工复核",
                    "actual_cost_cny": "1140.00",
                },
            ),
            ("complete", {"result": "验收复核通过；此为模拟任务记录"}),
        ]:
            task = command(
                "/tasks/" + task_id,
                {"expected_version": task["version"], "action": action, **details},
                method="PATCH",
            )
        check(
            task["state"] == "completed" and task["version"] == 4,
            "create/start/submit/complete durable lifecycle",
        )
        check(
            c.get(base + "/tasks/" + task_id + "/history", headers=h).json()["total"]
            == 4,
            "four atomic business audit records",
        )
        stale = c.patch(
            base + "/tasks/" + task_id,
            headers={**h, "Idempotency-Key": uuid.uuid4().hex},
            json={"expected_version": 1, "action": "start"},
        )
        check(
            stale.status_code == 409
            and stale.json()["error"]["code"] == "version_conflict",
            "stale version rejected with stable code",
        )
        report = command("/reports", {"kind": "risk", "format": "xlsx"})
        download = c.get(base + "/reports/" + report["id"] + "/download", headers=h)
        download.raise_for_status()
        check(
            hashlib.sha256(download.content).hexdigest() == report["sha256"],
            "authenticated real XLSX bytes and hash",
        )
        book = load_workbook(
            io.BytesIO(download.content), read_only=True, data_only=False
        )
        rows = list(book["Orders"].values)
        total = sum((Decimal(r[2]) for r in rows[1:]), Decimal(0))
        book.close()
        check(
            f"{total:.2f}" == report["summary"]["exposure_amount_cny"],
            "downloaded unique-order exposure independently sums correctly",
        )
        (OUT / "http-risk-report.xlsx").write_bytes(download.content)
        evaluation = command("/reports", {"kind": "evaluation", "format": "csv"})
        check(
            evaluation["summary"]["source"] == "public_historical",
            "public evaluation remains independent from manufacturing",
        )
        subscription = command(
            "/subscriptions",
            {
                "name": "P5验收本地订阅" + stamp,
                "topics": ["task.created", "task.updated", "report.created"],
            },
        )
        events = c.get(
            base + "/subscriptions/" + subscription["id"] + "/events", headers=h
        ).json()
        check(
            events["external_sent"] is False and len(events["items"]) > 0,
            "local-only events can be replayed",
        )
        check(
            c.get(
                base + "/subscriptions/" + subscription["id"] + "/events", headers=h
            ).json()
            == events,
            "replay stable at same cursor",
        )
        following = c.get(
            base + "/subscriptions/" + subscription["id"] + "/events",
            params={"after": events["next_cursor"]},
            headers=h,
        ).json()
        check(
            all(item["id"] > events["next_cursor"] for item in following["items"]),
            "cursor never replays already-consumed events",
        )
        spec = c.get(base + "/openapi", headers=h).json()
        check(
            "/api/v1/workspace/tasks" in spec["paths"],
            "enterprise endpoints available in OpenAPI",
        )
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "http-smoke.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "api_process": {"pid": service["pid"], "birth": service["birth"]},
                "checks": checks,
                "task_id": task_id,
                "record_id": record_id,
                "report_id": report["id"],
                "report_sha256": report["sha256"],
                "batch_id": batch["id"],
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
