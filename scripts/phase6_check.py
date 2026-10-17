#!/usr/bin/env python3
"""Final bounded suite, production build and sequential browser regressions."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase5_check as suite  # noqa: E402

checks = suite.checks
checks.OUTPUT = checks.ROOT / ".local/acceptance/phase-6"

if __name__ == "__main__":
    if "--browser" in sys.argv:
        raise SystemExit(checks.run_browser("phase6_browser.mjs"))
    if "--regression" in sys.argv:
        for phase in (1, 2, 3, 4, 5):
            os.environ["SUPPLYGUARD_BROWSER_OUTPUT"] = (
                f".local/acceptance/phase-6/p{phase}-regression"
            )
            result = checks.run_browser(f"phase{phase}_browser.mjs")
            if result:
                raise SystemExit(result)
        raise SystemExit(0)
    import subprocess
    import re

    checks.constrain_cpu()
    result = subprocess.call(
        [str(checks.PYTHON), "scripts/phase5_db.py", "prepare-tests"],
        cwd=checks.ROOT,
        env=checks.bounded_environment(),
    )
    if result:
        raise SystemExit(result)
    checks.changed_python = suite.targets
    result = checks.run([f"tests/phase{p}" for p in range(1, 6)])
    for file in checks.OUTPUT.glob("*.log"):
        file.write_text(
            re.sub(
                r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                "<redacted-test-auth>",
                file.read_text(errors="replace"),
            )
        )
    raise SystemExit(result)
