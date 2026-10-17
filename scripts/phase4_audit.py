#!/usr/bin/env python3
"""Read-only verification of active experiment artifacts, availability and test lock."""

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
for key in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"]:
    os.environ[key] = "2"
if hasattr(os, "sched_getaffinity"):
    os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:2]))
os.nice(10)


def main():
    import pandas as pd
    from packages.prediction import runtime
    from packages.prediction.data import split_manifest
    from packages.benchmarks.enterprise_validation import validate

    checks = []

    def check(ok, label):
        if not ok:
            raise AssertionError(label)
        checks.append(label)
        print("PASS", label, flush=True)

    directory, manifest, active = runtime.active_directory()
    for name in manifest:
        runtime.checked_file(name)
    check(True, "all active artifact SHA256 checks")
    r = runtime.report()
    for path, expected in r["source_hashes"].items():
        check(
            hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected,
            "training source " + path,
        )
    orders = pd.read_csv(
        runtime.checked_file("order-splits.csv"), parse_dates=["placed", "mature"]
    )
    check(orders.case_id.is_unique, "each order assigned exactly once")
    protocol = json.loads(runtime.checked_file("protocol.json").read_text())
    for split, limit in [
        ("train", "train_end"),
        ("validation", "validation_end"),
        ("test", "audit_end"),
    ]:
        g = orders[orders.split == split]
        check(
            (g.mature < pd.Timestamp(protocol[limit])).all(), "mature labels " + split
        )
    check(
        split_manifest(orders) == r["splits"],
        "recomputed split count/prevalence/time/ID hashes",
    )
    for name, g in orders[orders.split != "excluded"].groupby("split"):
        if name == "train":
            valid = g.placed < pd.Timestamp(protocol["train_end"])
        elif name == "validation":
            valid = (g.placed >= pd.Timestamp(protocol["train_end"])) & (
                g.placed < pd.Timestamp(protocol["validation_end"])
            )
        else:
            valid = (g.placed >= pd.Timestamp(protocol["validation_end"])) & (
                g.placed < pd.Timestamp(protocol["test_end"])
            )
        check(valid.all(), "chronological range " + name)
    selected = max(r["candidates"], key=lambda c: c["validation_ap"])
    # JSON sorting may change iteration order, but all scores are distinct in this run.
    check(selected == r["selection"], "champion chosen by validation AP only")
    m = r["models"][selected["name"]]["test"]
    check(
        all(v["test"]["count"] == m["count"] for v in r["models"].values()),
        "all candidates share the same test cohort",
    )
    for case in runtime.cases():
        prediction = runtime.predict(case["case_id"], r["domain"])
        check(
            abs(prediction["probability"] - case["probability"]) < 1e-12,
            "actual model inference " + case["case_id"],
        )
    contracts = validate()
    check(
        contracts["status"] == "passed",
        "offline scorer and enterprise policy contracts",
    )
    proof_path = ROOT / ".local/prediction/reproduction.json"
    check(
        proof_path.exists(),
        "reproduction evidence exists; run make phase4-reproduce first",
    )
    if proof_path.exists():
        proof = json.loads(proof_path.read_text())
        check(
            proof["status"] == "passed" and proof["compared_to"] == active["run_id"],
            "active experiment reproduced without test retuning",
        )
    else:
        print(
            "NOT RUN reproduction; make phase4-reproduce before acceptance", flush=True
        )
    output = ROOT / ".local/acceptance/phase-4"
    output.mkdir(parents=True, exist_ok=True)
    (output / "artifact-audit.json").write_text(
        json.dumps(
            {
                "status": "passed",
                "run_id": active["run_id"],
                "checks": checks,
                "reproduction_present": proof_path.exists(),
            },
            indent=2,
        )
        + "\n"
    )
    (output / "evaluation-contracts.json").write_text(
        json.dumps(contracts, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        "MODEL",
        selected["name"],
        "TEST AP",
        m["average_precision"],
        "Recall@10%",
        m["ranking"]["10"]["recall"],
    )


if __name__ == "__main__":
    main()
