#!/usr/bin/env python3
"""No network, CPU-only fixed experiment; immutable run directories."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reproduce", action="store_true")
    args = parser.parse_args()
    if hasattr(os, "sched_getaffinity"):
        os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
    os.nice(10)
    import resource

    memory_limit = 4 * 1024**3
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    for key in [
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ]:
        os.environ[key] = "2"
    os.environ["MPLCONFIGDIR"] = str(ROOT / ".local/prediction/matplotlib")
    from packages.prediction.experiment import train, dump

    base = ROOT / ".local/prediction"
    active = base / "active.json"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    output = base / "experiments" / stamp
    report = train(output)
    if args.reproduce:
        if not active.exists():
            raise RuntimeError("No active experiment to reproduce")
        previous = base / "experiments" / json.loads(active.read_text())["run_id"]
        checks = {
            f: hashlib.sha256((previous / f).read_bytes()).hexdigest()
            == hashlib.sha256((output / f).read_bytes()).hexdigest()
            for f in [
                "protocol.json",
                "source-hashes.json",
                "runtime.json",
                "order-splits.csv",
                "split-manifest.json",
                "selection.json",
                "test-predictions.csv",
                "test-all-model-predictions.json",
            ]
        }
        proof = {
            "run_id": stamp,
            "compared_to": previous.name,
            "checks": checks,
            "status": "passed" if all(checks.values()) else "failed",
        }
        dump(base / "reproduction.json", proof)
        print(json.dumps(proof))
        if not all(checks.values()):
            return 1
    else:
        next_active = base / ("active-" + stamp + ".json")
        dump(
            next_active,
            {
                "run_id": stamp,
                "report_sha256": hashlib.sha256(
                    (output / "report.json").read_bytes()
                ).hexdigest(),
                "manifest_sha256": hashlib.sha256(
                    (output / "manifest.json").read_bytes()
                ).hexdigest(),
                "protocol": report["protocol_version"],
            },
        )
        next_active.replace(active)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
