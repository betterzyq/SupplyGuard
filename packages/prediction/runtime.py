"""Authenticated public-benchmark views. No tenant business data or arbitrary model paths."""

from __future__ import annotations
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from .data import ROOT

BASE = ROOT / ".local/prediction"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_directory():
    active = json.loads((BASE / "active.json").read_text())
    run_id = active["run_id"]
    if not re.fullmatch(r"\d{8}T\d{12}", run_id):
        raise ValueError("Invalid trusted run ID")
    directory = BASE / "experiments" / run_id
    if digest(directory / "manifest.json") != active["manifest_sha256"]:
        raise ValueError("Artifact manifest integrity failure")
    manifest = json.loads((directory / "manifest.json").read_text())
    return directory, manifest, active


def checked_file(name):
    directory, manifest, _ = active_directory()
    if name not in manifest or "/" in name or "\\" in name:
        raise ValueError("Unknown artifact")
    path = directory / name
    if digest(path) != manifest[name]:
        raise ValueError("Artifact checksum mismatch: " + name)
    return path


def report():
    value = json.loads(checked_file("report.json").read_text())
    _, _, active = active_directory()
    value["run_id"] = active["run_id"]
    value["model_version"] = active["run_id"] + ":" + value["selection"]["name"]
    return value


def cases():
    return json.loads(checked_file("cases.json").read_text())


@lru_cache(maxsize=1)
def model(path, checksum):
    import joblib

    if digest(Path(path)) != checksum:
        raise ValueError("Model integrity failure")
    return joblib.load(
        path
    )  # trusted local training artifact only; never client-supplied


def predict(case_id, domain):
    if domain != "dataco-retail-historical":
        raise ValueError("Domain unsupported; manufacturing transfer is unvalidated")
    case = next((r for r in cases() if r["case_id"] == case_id), None)
    if case is None:
        raise KeyError("Unknown historical case; manufacturing orders are unsupported")
    config = json.loads(checked_file("runtime.json").read_text())
    selected = config["selected"]
    f = case["features"]
    if selected == "global_train_rate":
        probability = config["global_rate"]
    elif selected == "mature_product_history":
        probability = f["history_rate"]
    elif selected == "fixed_shipping_rule":
        probability = max(0.05, min(0.95, 0.25 + 0.15 * (4 - f["planned_min"])))
    else:
        import pandas as pd
        from threadpoolctl import threadpool_limits

        path = checked_file("model.joblib")
        with threadpool_limits(limits=2):
            bundle = model(str(path), digest(path))
            matrix = bundle["preprocessor"].transform(pd.DataFrame([f]))
            estimator = bundle["model"]
            probability = float(
                estimator.booster_.predict(matrix, num_threads=2)[0]
                if hasattr(estimator, "booster_")
                else estimator.predict_proba(matrix)[0, 1]
            )
    _, _, active = active_directory()
    return {
        "case_id": case_id,
        "probability": probability,
        "threshold": config["threshold"],
        "predicted_late": probability >= config["threshold"],
        "domain": domain,
        "source_type": "public_historical",
        "model_version": active["run_id"] + ":" + selected,
        "features": f,
        "feature_evidence": case["evidence"],
        "unknown_categories": case["unknown_categories"],
        "observed_label_for_review": case["label"],
        "limitations": [
            "Historical retail validation only; no manufacturing transfer validation.",
            "Feature availability uses assumed observation lag; no live ERP or carrier feed.",
        ],
    }
