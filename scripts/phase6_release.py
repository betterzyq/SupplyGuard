#!/usr/bin/env python3
"""Local delivery snapshots; no git reset, schema change or automatic restore."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase1_check import ROOT, constrain_cpu, frontend_fingerprint  # noqa: E402

OUT = ROOT / ".local/acceptance/phase-6"
RELEASE = ROOT / ".local/releases"


def source_paths():
    paths = (
        subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    return sorted(
        {
            p
            for p in paths
            if p
            and (ROOT / p).is_file()
            and not (ROOT / p).is_symlink()
            and not any(
                part.startswith(".env")
                or part in {".local", "node_modules", ".git", ".venv"}
                or part.endswith((".pem", ".key"))
                for part in Path(p).parts
            )
        }
    )


def checkpoint():
    """Capture accepted production web artifact and current DB before upgrading web."""
    target = RELEASE / "p5-accepted"
    if (target / "checkpoint.json").exists():
        print("P5 checkpoint already exists; preserved")
        return
    expected = json.loads(
        (ROOT / ".local/acceptance/phase-5/source-snapshot.json").read_text()
    )["frontend_fingerprint"]
    stamp = (ROOT / ".local/acceptance/services/frontend-fingerprint.txt").read_text()
    if expected != stamp:
        raise RuntimeError(
            "Installed web is not the accepted P5 fingerprint; refusing mislabeled backup"
        )
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    bundle = target / "web-build.tar.gz"
    with tarfile.open(bundle, "w:gz", compresslevel=1) as tar:

        def exclude_cache(info):
            return (
                None if "/cache/" in info.name or info.name.endswith("/cache") else info
            )

        tar.add(
            ROOT / "apps/web/.next-acceptance",
            arcname=".next-acceptance",
            filter=exclude_cache,
        )
    bundle.chmod(0o600)
    from phase5_db import config

    u = config()
    env = os.environ.copy()
    env.update(
        PGHOST=u.host,
        PGPORT=str(u.port or 5432),
        PGUSER=u.username,
        PGPASSWORD=u.password,
        PGDATABASE=u.database,
    )
    dump = target / "before-p6.dump"
    p = subprocess.run(
        [
            str(ROOT / ".local/runtime/bin/pg_dump"),
            "--format=custom",
            "--file",
            str(dump),
        ],
        env=env,
        capture_output=True,
    )
    if p.returncode:
        raise RuntimeError("SupplyGuard backup failed; connection details redacted")
    dump.chmod(0o600)
    p = subprocess.run(
        [str(ROOT / ".local/runtime/bin/pg_restore"), "--list", str(dump)],
        capture_output=True,
    )
    if p.returncode:
        raise RuntimeError("Backup catalog invalid")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "frontend_fingerprint": expected,
        "web_build_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "database_sha256": hashlib.sha256(dump.read_bytes()).hexdigest(),
        "database_catalog_verified": True,
        "restore_test": "P5 original backup restored in isolated DB; this newer dump catalog verified only",
        "scope": "P5 production frontend artifact and pre-P6 database, not a complete P5 source archive",
    }
    (target / "checkpoint.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("PASS preserved accepted P5 production web and pre-P6 SupplyGuard DB")


def snapshot():
    OUT.mkdir(parents=True, exist_ok=True)
    RELEASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths = source_paths()
    hashes = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}
    bundle = RELEASE / "p6-source.tar.gz"
    with tarfile.open(bundle, "w:gz", compresslevel=1) as tar:
        for p in paths:
            tar.add(ROOT / p, arcname=p, recursive=False)
    bundle.chmod(0o600)
    manifest = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "working_tree_uncommitted": True,
        "file_count": len(paths),
        "frontend_fingerprint": frontend_fingerprint(),
        "source_bundle": str(bundle.relative_to(ROOT)),
        "source_bundle_sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "excludes": ".env*, keys, symlinks, .local, external data, environments, dependencies; not a complete data/runtime backup",
        "sha256": hashes,
    }
    (OUT / "source-snapshot.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f"PASS source delivery snapshot: {len(paths)} files; no environment or raw external data"
    )


if __name__ == "__main__":
    constrain_cpu()
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint-p5", action="store_true")
    args = parser.parse_args()
    checkpoint() if args.checkpoint_p5 else snapshot()
