#!/usr/bin/env python3
"""Final evidence + source/build identity + front-end secret exposure audit."""

import hashlib
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase1_check import ROOT, frontend_fingerprint, constrain_cpu  # noqa: E402
from acceptance_services import load_record, owns_process  # noqa: E402

OUT = ROOT / ".local/acceptance/phase-6"


def main():
    constrain_cpu()
    checks = []

    def check(ok, label):
        assert ok, label
        checks.append(label)
        print("PASS", label, flush=True)

    for name in ["checks.json", "http-smoke.json", "browser.json"] + [
        f"p{p}-regression/browser.json" for p in range(1, 6)
    ]:
        proof = json.loads((OUT / name).read_text())
        check(proof["status"] == "passed", "passed " + name)
    for phase in (4, 5):
        proof = json.loads(
            (ROOT / f".local/acceptance/phase-{phase}/artifact-audit.json").read_text()
        )
        check(proof["status"] == "passed", f"P{phase} model/workspace artifact audit")
    source = json.loads((OUT / "source-snapshot.json").read_text())
    check(
        all(
            (ROOT / p).is_file()
            and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == h
            for p, h in source["sha256"].items()
        ),
        "delivered source hashes unchanged",
    )
    bundle = ROOT / source["source_bundle"]
    check(
        hashlib.sha256(bundle.read_bytes()).hexdigest()
        == source["source_bundle_sha256"],
        "source archive SHA256 intact",
    )
    fingerprint = frontend_fingerprint()
    check(
        source["frontend_fingerprint"]
        == fingerprint
        == (ROOT / ".local/acceptance/services/frontend-fingerprint.txt").read_text(),
        "source snapshot equals installed frontend build fingerprint",
    )
    for name in ("api", "web"):
        check(owns_process(name, load_record(name)), "owned acceptance process " + name)
    checkpoint = ROOT / ".local/releases/p5-accepted"
    manifest = json.loads((checkpoint / "checkpoint.json").read_text())
    for name, field in [
        ("web-build.tar.gz", "web_build_sha256"),
        ("before-p6.dump", "database_sha256"),
    ]:
        check(
            hashlib.sha256((checkpoint / name).read_bytes()).hexdigest()
            == manifest[field],
            "P5 accepted checkpoint intact " + name,
        )
    from dotenv import dotenv_values

    config = {**dotenv_values(ROOT / ".env"), **os.environ}
    secret_values = [
        str(v).encode()
        for k, v in config.items()
        if v
        and len(str(v)) >= 12
        and any(
            t in k.upper()
            for t in ("SECRET", "PASSWORD", "API_KEY", "POSTGRES_URL", "DATABASE_URL")
        )
        and not k.startswith("NEXT_PUBLIC_")
    ]
    exposed = False
    chunks = list((ROOT / "apps/web/.next-acceptance/static").rglob("*.js"))
    for p in chunks:
        content = p.read_bytes()
        if any(value in content for value in secret_values):
            exposed = True
    check(
        bool(chunks) and not exposed,
        "configured backend secret values absent from shipped browser JavaScript",
    )
    for p in (ROOT / "apps/web/src").rglob("*"):
        if p.is_file():
            import re

            public = re.findall(
                r"process\.env\.(NEXT_PUBLIC_[A-Z0-9_]+)", p.read_text()
            )
            check(
                all(k == "NEXT_PUBLIC_API_BASE_URL" for k in public),
                "public environment allowlist " + str(p.relative_to(ROOT)),
            ) if public else None
    (OUT / "artifact-audit.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "checks": checks,
                "source_files": source["file_count"],
                "note": "Not user final acceptance; secret check covers configured long backend secret values, not a complete security review",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
