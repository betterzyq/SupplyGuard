#!/usr/bin/env python3
"""Owned isolated migration test; verified backup before additive project upgrade."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DEBUG"] = "false"
from packages.common.config import get_settings  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
import psycopg2  # noqa: E402
from psycopg2 import sql  # noqa: E402

OUT = ROOT / ".local/acceptance/phase-5"
BASE = "e5f6a7b8c9d0"
HEAD = "f6a7b8c9d0e1"


def config():
    u = make_url(get_settings().POSTGRES_URL)
    if u.database != "supplyguard":
        raise RuntimeError(
            "Expected SupplyGuard project database; refusing other database"
        )
    return u


def connect(database=None):
    u = config()
    return psycopg2.connect(
        host=u.host,
        port=u.port or 5432,
        user=u.username,
        password=u.password,
        dbname=database or u.database,
        connect_timeout=5,
    )


def migrate(database, target):
    u = config().set(database=database)
    env = os.environ.copy()
    env["DEBUG"] = "false"
    env["POSTGRES_URL"] = u.render_as_string(hide_password=False)
    p = subprocess.run(
        [
            str(ROOT / ".venv/bin/alembic"),
            "upgrade" if target == "head" else "downgrade",
            target,
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if p.returncode:
        # Avoid exception output with credentials/URLs; log only migration messages.
        lines = [
            x
            for x in (p.stdout + p.stderr).splitlines()
            if x.startswith(("INFO", "ERROR"))
        ]
        raise RuntimeError("Migration failed: " + " ".join(lines)[-1000:])


def inspect(database):
    with connect(database) as c, c.cursor() as q:
        q.execute("select version_num from alembic_version")
        rev = q.fetchone()[0]
        q.execute(
            "select tablename from pg_tables where schemaname='public' order by tablename"
        )
        return rev, [x[0] for x in q.fetchall()]


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    name = "supplyguard_p5_test_" + uuid.uuid4().hex[:10]
    c = connect()
    c.autocommit = True
    with c.cursor() as q:
        q.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    c.close()
    (OUT / "test-db.json").write_text(
        json.dumps(
            {
                "name": name,
                "owner": "phase5_db.py",
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n"
    )
    migrate(name, "head")
    up, first = inspect(name)
    assert up == HEAD and len([x for x in first if x.startswith("sg5_")]) == 9
    migrate(name, BASE)
    down, middle = inspect(name)
    assert down == BASE and not any(x.startswith("sg5_") for x in middle)
    migrate(name, "head")
    final, last = inspect(name)
    assert final == HEAD and first == last
    result = {
        "status": "passed",
        "database": name,
        "upgrade": up,
        "downgrade": down,
        "reupgrade": final,
        "new_tables": [x for x in last if x.startswith("sg5_")],
        "legacy_tables_unchanged_on_downgrade": set(middle)
        == set(last) - {x for x in last if x.startswith("sg5_")},
    }
    (OUT / "migration-test.json").write_text(json.dumps(result, indent=2) + "\n")
    print("PASS isolated PostgreSQL upgrade/downgrade/reupgrade:", name, flush=True)


def pg_environment(database):
    u = config()
    env = os.environ.copy()
    env.update(
        PGHOST=u.host or "localhost",
        PGPORT=str(u.port or 5432),
        PGUSER=u.username,
        PGPASSWORD=u.password,
        PGDATABASE=database,
    )
    return env


def apply():
    proof = json.loads((OUT / "migration-test.json").read_text())
    if proof["status"] != "passed" or not proof["legacy_tables_unchanged_on_downgrade"]:
        raise RuntimeError("Isolated migration proof required")
    revision, tables = inspect(config().database)
    if revision == HEAD:
        print("ALREADY APPLIED P5 additive schema")
        return
    if revision != BASE:
        raise RuntimeError("Unexpected project migration revision")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    backup = OUT / ("before-p5-" + stamp + ".dump")
    dump = ROOT / ".local/runtime/bin/pg_dump"
    restore = ROOT / ".local/runtime/bin/pg_restore"
    env = pg_environment(config().database)
    p = subprocess.run(
        [str(dump), "--format=custom", "--file", str(backup)],
        env=env,
        capture_output=True,
    )
    if p.returncode:
        raise RuntimeError("Project backup failed; schema unchanged")
    os.chmod(backup, 0o600)
    p = subprocess.run([str(restore), "--list", str(backup)], capture_output=True)
    if p.returncode or backup.stat().st_size < 1000:
        raise RuntimeError("Backup archive validation failed")
    migrate(config().database, "head")
    after, final = inspect(config().database)
    assert after == HEAD and set(tables) <= set(final)
    result = {
        "status": "passed",
        "before": revision,
        "after": after,
        "backup": str(backup.relative_to(ROOT)),
        "backup_bytes": backup.stat().st_size,
        "backup_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        "archive_list_verified": True,
        "added_tables": sorted(set(final) - set(tables)),
        "existing_tables_preserved": True,
    }
    (OUT / "migration-apply.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        "PASS project backup verified and additive P5 upgrade; existing tables preserved",
        flush=True,
    )


def verify_backup():
    proof = json.loads((OUT / "migration-apply.json").read_text())
    backup = ROOT / proof["backup"]
    if hashlib.sha256(backup.read_bytes()).hexdigest() != proof["backup_sha256"]:
        raise RuntimeError("Backup hash mismatch")
    name = "supplyguard_p5_restore_" + uuid.uuid4().hex[:10]
    c = connect()
    c.autocommit = True
    with c.cursor() as q:
        q.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    c.close()
    restored = subprocess.run(
        [
            str(ROOT / ".local/runtime/bin/pg_restore"),
            "--exit-on-error",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            name,
            str(backup),
        ],
        env=pg_environment(name),
        capture_output=True,
    )
    if restored.returncode:
        raise RuntimeError(
            "Backup restore failed in owned isolated database; project unchanged"
        )
    revision, tables = inspect(name)
    if revision != BASE or any(t.startswith("sg5_") for t in tables):
        raise RuntimeError("Restored pre-P5 schema is not the expected base")
    with connect(name) as restored_connection, restored_connection.cursor() as q:
        q.execute("select count(*) from users")
        users = q.fetchone()[0]
        q.execute("select count(*) from tenants")
        tenants = q.fetchone()[0]
    if not users or not tenants:
        raise RuntimeError("Restored core data missing")
    (OUT / "backup-restore.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "database": name,
                "owner": "phase5_db.py",
                "backup_sha256": proof["backup_sha256"],
                "revision": revision,
                "tables": len(tables),
                "core_users_nonempty": True,
                "core_tenants_nonempty": True,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        "PASS actual backup restore into isolated owned database; project unchanged",
        flush=True,
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["prepare-tests", "apply", "verify-backup"])
    a = p.parse_args()
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    os.nice(10)
    {"prepare-tests": prepare, "apply": apply, "verify-backup": verify_backup}[
        a.action
    ]()
