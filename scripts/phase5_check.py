#!/usr/bin/env python3
"""Bounded P5 PostgreSQL integration, accepted regression and production build."""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase1_check as checks  # noqa: E402

checks.OUTPUT = checks.ROOT / ".local/acceptance/phase-5"
original = checks.changed_python


def targets():
    extra = [
        "packages/operations",
        "packages/common/db/models/workspace.py",
        "apps/api/main.py",
        "apps/api/routers/v1/workspace.py",
        "tests/phase5",
        "scripts/phase5_check.py",
        "scripts/phase5_db.py",
        "scripts/phase5_smoke.py",
        "scripts/phase5_audit.py",
        "scripts/workspace_api_example.py",
        "alembic/versions/f6a7b8c9d0e1_add_enterprise_workspace.py",
    ]
    return sorted(set(original() + [str(checks.ROOT / p) for p in extra]))


if __name__ == "__main__":
    if "--browser" in sys.argv:
        raise SystemExit(checks.run_browser("phase5_browser.mjs"))
    checks.constrain_cpu()
    p = subprocess.run(
        [str(checks.PYTHON), "scripts/phase5_db.py", "prepare-tests"],
        cwd=checks.ROOT,
        env=checks.bounded_environment(),
    )
    if p.returncode:
        raise SystemExit(p.returncode)
    checks.changed_python = targets
    result = checks.run(
        ["tests/phase1", "tests/phase2", "tests/phase3", "tests/phase4", "tests/phase5"]
    )
    for file in checks.OUTPUT.glob("*.log"):
        data = file.read_text(errors="replace")
        file.write_text(
            re.sub(
                r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                "<redacted-test-auth>",
                data,
            )
        )
    raise SystemExit(result)
