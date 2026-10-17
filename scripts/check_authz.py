#!/usr/bin/env python3
"""Run the current two-role policy regression; legacy department tests are retired."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    print(
        "SupplyGuard enterprise-v2 authorization regression (no seed/reset)", flush=True
    )
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/phase1/test_policy.py",
                "tests/phase1/test_api.py",
                "-q",
            ],
            cwd=ROOT,
        )
    )
