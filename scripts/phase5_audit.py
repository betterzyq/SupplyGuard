#!/usr/bin/env python3
"""Project-local read-only backup/schema/tenant/activity and persistence evidence audit."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from phase5_db import connect, HEAD  # noqa: E402

OUT = ROOT / ".local/acceptance/phase-5"


def main():
    checks = []

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS", label, flush=True)

    proof = json.loads((OUT / "migration-apply.json").read_text())
    restored = json.loads((OUT / "backup-restore.json").read_text())
    check(
        restored["status"] == "passed"
        and restored["backup_sha256"] == proof["backup_sha256"],
        "actual isolated backup restore verified",
    )
    backup = ROOT / proof["backup"]
    check(
        proof["status"] == "passed"
        and hashlib.sha256(backup.read_bytes()).hexdigest() == proof["backup_sha256"],
        "pre-migration backup SHA256 intact",
    )
    check(
        json.loads((OUT / "migration-test.json").read_text())["status"] == "passed",
        "isolated PostgreSQL upgrade/downgrade/reupgrade proof",
    )
    with connect() as c, c.cursor() as q:
        q.execute("select version_num from alembic_version")
        check(q.fetchone()[0] == HEAD, "project at additive P5 revision")
        q.execute(
            "select count(*) from pg_tables where schemaname='public' and tablename like 'sg5_%'"
        )
        check(q.fetchone()[0] == 9, "all nine workspace tables present")
        q.execute(
            "select count(*) from sg5_links l join sg5_records s on s.id=l.source_id join sg5_records t on t.id=l.target_id where l.tenant_id<>s.tenant_id or l.tenant_id<>t.tenant_id"
        )
        check(q.fetchone()[0] == 0, "no cross-tenant record links")
        q.execute(
            "select count(*) from sg5_tasks t join sg5_records r on r.id=t.record_id where t.tenant_id<>r.tenant_id"
        )
        check(q.fetchone()[0] == 0, "no cross-tenant task sources")
        q.execute(
            "select count(*) from sg5_records r join sg5_import_batches b on b.id=r.import_batch_id where b.state<>'confirmed' or b.tenant_id<>r.tenant_id"
        )
        check(
            q.fetchone()[0] == 0,
            "business records only belong to confirmed same-tenant import batches",
        )
        q.execute(
            "select count(*) from sg5_tasks t where not exists (select 1 from sg5_activity a where a.tenant_id=t.tenant_id and a.resource_id=t.id::text and a.action='task.created')"
        )
        check(q.fetchone()[0] == 0, "every task has atomic creation audit")
        q.execute(
            "select count(*) from sg5_records where source_type not in ('synthetic','enterprise_uploaded','public_historical')"
        )
        check(q.fetchone()[0] == 0, "all business data has explicit source type")
        q.execute("select content,sha256 from sg5_reports")
        valid = True
        while (row := q.fetchone()) is not None:
            value, expected = row
            valid = valid and hashlib.sha256(bytes(value)).hexdigest() == expected
        check(
            valid,
            "all persisted report bytes match stored SHA256",
        )
    for name in ["http-smoke.json", "restart-verification.json", "browser.json"]:
        path = OUT / name
        check(
            path.exists() and json.loads(path.read_text())["status"] == "passed",
            "passed " + name,
        )
    (OUT / "artifact-audit.json").write_text(
        json.dumps({"status": "passed", "checks": checks}, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
