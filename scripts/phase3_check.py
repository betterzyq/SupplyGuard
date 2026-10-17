#!/usr/bin/env python3
"""P3 includes accepted P1/P2 regression and isolated production build."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase1_check as checks  # noqa: E402

checks.OUTPUT = checks.ROOT / ".local/acceptance/phase-3"
if __name__ == "__main__":
    raise SystemExit(
        checks.run_browser("phase3_browser.mjs")
        if "--browser" in sys.argv
        else checks.run(["tests/phase1", "tests/phase2", "tests/phase3"])
    )
