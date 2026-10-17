#!/usr/bin/env python3
"""P4 scorer/leakage/auth tests, P1–P3 regression, bounded production build."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import phase1_check as checks  # noqa: E402

checks.OUTPUT = checks.ROOT / ".local/acceptance/phase-4"
base_changed_python = checks.changed_python


def phase4_python():
    stable = [
        "packages/prediction",
        "packages/benchmarks",
        "tests/phase4",
        "apps/api/routers/v1/prediction.py",
    ]
    stable += [
        "scripts/" + name + ".py"
        for name in [
            "phase4_check",
            "phase4_train",
            "phase4_audit",
            "phase4_smoke",
            "fetch_phase4_data",
            "generate_phase4_gold",
            "prepare_phase4_rag_gold",
            "run_benchmark",
        ]
    ]
    return sorted(set(base_changed_python() + [str(checks.ROOT / p) for p in stable]))


checks.changed_python = phase4_python
if __name__ == "__main__":
    raise SystemExit(
        checks.run_browser("phase4_browser.mjs")
        if "--browser" in sys.argv
        else checks.run(
            ["tests/phase1", "tests/phase2", "tests/phase3", "tests/phase4"]
        )
    )
