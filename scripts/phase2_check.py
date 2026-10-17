#!/usr/bin/env python3
"""P2 checks include the accepted P1 regression and isolated frontend build."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase1_check as checks  # noqa: E402

checks.OUTPUT = checks.ROOT / ".local/acceptance/phase-2"
if __name__ == "__main__":
    raise SystemExit(
        checks.run_browser("phase2_browser.mjs")
        if "--browser" in sys.argv
        else checks.run(["tests/phase1", "tests/phase2"])
    )
