"""Fixed-budget CPU experiment. All model/threshold selection precedes test scoring."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import time
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.metrics import average_precision_score

from .data import (
    ROOT,
    PROTOCOL,
    BASE_NUM,
    CATS,
    HISTORY,
    GRAPH,
    prepare,
    add_features,
    split_manifest,
)
from .metrics import evaluate, threshold_from_validation, bootstrap


def dump(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        + "\n"
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def predict_probability(model, matrix):
    return (
        model.booster_.predict(matrix, num_threads=2)
        if isinstance(model, lgb.LGBMClassifier)
        else model.predict_proba(matrix)[:, 1]
    )


def train(output: Path):
    start = time.perf_counter()
    protocol = json.loads(PROTOCOL.read_text())
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "protocol.json", protocol)
    source_files = sorted((ROOT / "packages/prediction").glob("*.py")) + [
        ROOT / "scripts/phase4_train.py",
        PROTOCOL,
        ROOT / "data/catalog/dataco-v5.json",
        ROOT / "requirements/phase4-ml.txt",
        ROOT / "requirements/phase4-runtime-lock.txt",
        ROOT / "data/catalog/dataco-test-lock-v1.json",
    ]
    dump(
        output / "source-hashes.json",
        {str(p.relative_to(ROOT)): sha(p) for p in source_files},
    )
    raw = ROOT / "data/external/dataco-v5/DataCoSupplyChainDataset.csv"
    catalog = json.loads((ROOT / "data/catalog/dataco-v5.json").read_text())
    raw_sha = sha(raw)
    expected = next(x["sha256"] for x in catalog["files"] if x["filename"] == raw.name)
    if raw_sha != expected:
        raise ValueError("Source hash mismatch")
    print("AUDIT order aggregation and availability features", flush=True)
    orders, audit = prepare(raw)
    orders = add_features(orders)
    split = split_manifest(orders)
    lock = json.loads((ROOT / "data/catalog/dataco-test-lock-v1.json").read_text())
    if lock["protocol_sha256"] != sha(PROTOCOL) or lock["source_sha256"] != raw_sha:
        raise ValueError(
            "Frozen protocol/data changed; define and review a new experiment version"
        )
    for name, expected_split in lock["splits"].items():
        if any(split[name][k] != v for k, v in expected_split.items()):
            raise ValueError("Locked order split changed before fitting: " + name)
    dump(output / "audit.json", audit)
    dump(output / "split-manifest.json", split)
    orders[["case_id", "placed", "mature", "split", "target"]].to_csv(
        output / "order-splits.csv", index=False
    )
    trainf, val, test = [
        orders[orders.split == s].copy() for s in ["train", "validation", "test"]
    ]
    assert not (
        set(trainf.case_id) & set(val.case_id)
        or set(trainf.case_id) & set(test.case_id)
        or set(val.case_id) & set(test.case_id)
    )
    if min(len(trainf), len(val), len(test)) < 100:
        raise ValueError("Insufficient chronological sample")
    # No full-data preprocessing. One encoder per feature ablation, fitted on train only.
    candidates = []
    pipelines = {}
    predictions = {}
    global_rate = float(trainf.target.mean())
    validation = {
        "global_train_rate": np.full(len(val), global_rate),
        "mature_product_history": val.history_rate.to_numpy(),
        "fixed_shipping_rule": np.clip(
            0.25 + 0.15 * (4 - val.planned_min.to_numpy()), 0.05, 0.95
        ),
    }
    groups = {
        "base": BASE_NUM,
        "history": BASE_NUM + HISTORY,
        "graph": BASE_NUM + HISTORY + GRAPH,
    }
    fit_count = 0
    for group, nums in groups.items():
        prep = ColumnTransformer(
            [
                (
                    "numeric",
                    make_pipeline(SimpleImputer(strategy="median"), StandardScaler()),
                    nums,
                ),
                (
                    "category",
                    OneHotEncoder(handle_unknown="ignore", min_frequency=10),
                    CATS,
                ),
            ],
            sparse_threshold=1.0,
        )
        xx = prep.fit_transform(trainf)
        vv = prep.transform(val)
        if group == "base":
            for c in protocol["budget"]["logistic_C"]:
                name = f"logistic_C{c}"
                model = LogisticRegression(
                    C=c, solver="liblinear", max_iter=500, random_state=protocol["seed"]
                )
                model.fit(xx, trainf.target)
                validation[name] = predict_probability(model, vv)
                pipelines[name] = {
                    "preprocessor": prep,
                    "model": model,
                    "numeric": nums,
                }
                fit_count += 1
        for leaves in protocol["budget"]["lightgbm_leaves"]:
            name = f"lightgbm_{group}_{leaves}"
            model = lgb.LGBMClassifier(
                n_estimators=protocol["budget"]["trees"],
                num_leaves=leaves,
                learning_rate=0.05,
                max_depth=-1,
                min_child_samples=40,
                n_jobs=2,
                random_state=protocol["seed"],
                deterministic=True,
                force_col_wise=True,
                verbosity=-1,
            )
            model.fit(xx, trainf.target)
            validation[name] = predict_probability(model, vv)
            pipelines[name] = {"preprocessor": prep, "model": model, "numeric": nums}
            fit_count += 1
        print("FIT", group, fit_count, flush=True)
    assert fit_count == protocol["budget"]["training_fits"]
    for name, p in validation.items():
        candidates.append(
            {
                "name": name,
                "validation_ap": float(average_precision_score(val.target, p)),
                "threshold": threshold_from_validation(val.target, p),
            }
        )
    champion = max(candidates, key=lambda x: x["validation_ap"])
    # Persist selection before accessing test labels in any metric computation.
    dump(
        output / "selection.json",
        {
            "candidates": candidates,
            "champion": champion,
            "training_fits": fit_count,
            "test_used_for_selection": False,
        },
    )
    selected = champion["name"]
    report = {
        "schema_version": "prediction-report-v1",
        "protocol_version": protocol["version"],
        "protocol_sha256": sha(PROTOCOL),
        "source_sha256": raw_sha,
        "domain": protocol["domain"],
        "source_type": "public_historical",
        "source": catalog,
        "audit": audit,
        "splits": split,
        "selection": champion,
        "candidates": candidates,
        "limitations": protocol["limitations"],
        "models": {},
        "compute": {
            "device": "cpu",
            "threads": 2,
            "cpu_affinity": "first two allowed cores",
            "gpu_used": False,
            "address_space_limit_gib": 4,
            "training_fits": fit_count,
        },
        "source_hashes": json.loads((output / "source-hashes.json").read_text()),
        "feature_allowlist": {
            "numeric": BASE_NUM,
            "categorical": CATS,
            "history": HISTORY,
            "graph": GRAPH,
        },
    }
    for name in validation:
        if name == "global_train_rate":
            p = np.full(len(test), global_rate)
        elif name == "mature_product_history":
            p = test.history_rate.to_numpy()
        elif name == "fixed_shipping_rule":
            p = np.clip(0.25 + 0.15 * (4 - test.planned_min.to_numpy()), 0.05, 0.95)
        else:
            bundle = pipelines[name]
            p = predict_probability(
                bundle["model"], bundle["preprocessor"].transform(test)
            )
        predictions[name] = p
        threshold = next(x["threshold"] for x in candidates if x["name"] == name)
        report["models"][name] = {
            "test": evaluate(test.target, p, test.quoted_amount, threshold)
        }
    amount = test.quoted_amount.to_numpy()
    report["models"]["quoted_amount_ranking"] = {
        "test": evaluate(test.target, amount, amount, probability=False)
    }
    p = predictions[selected]
    base_reference = max(
        [x for x in candidates if x["name"].startswith("lightgbm_base_")],
        key=lambda x: x["validation_ap"],
    )["name"]
    report["uncertainty"] = bootstrap(
        test,
        p,
        amount,
        protocol["seed"],
        protocol["bootstrap"]["resamples"],
        {
            "fixed_rule": predictions["fixed_shipping_rule"],
            "base_lightgbm": predictions[base_reference],
        },
    )
    report["uncertainty"]["base_reference"] = base_reference
    report["subgroups"] = {
        field: {
            str(v): evaluate(
                g.target,
                p[test.index.get_indexer(g.index)],
                g.quoted_amount,
                champion["threshold"],
            )
            for v, g in test.groupby(field)
        }
        for field in ["mode", "market", "month"]
    }
    # Validation-selected graph/history champions; test reported without further tuning.
    report["ablation"] = {
        group: max(
            [x for x in candidates if x["name"].startswith("lightgbm_" + group + "_")],
            key=lambda x: x["validation_ap"],
        )["name"]
        for group in groups
    }
    test["probability"] = p
    test["predicted_late"] = p >= champion["threshold"]
    failures = []
    for kind, mask in [
        ("false_positive", (test.target == 0) & test.predicted_late),
        ("false_negative", (test.target == 1) & ~test.predicted_late),
    ]:
        # Earliest cases, not cherry-picked for appearance.
        for _, r in test[mask].head(5).iterrows():
            failures.append(
                {
                    "case_id": r.case_id,
                    "kind": kind,
                    "probability": float(r.probability),
                    "label": int(r.target),
                    "mode": r["mode"],
                    "month": int(r.month),
                }
            )
    report["failure_cases"] = failures
    case_rows = []
    # A fixed historical review sample, plus failure examples, with no customer identifiers.
    ids = set(test.iloc[np.linspace(0, len(test) - 1, 20, dtype=int)].case_id) | {
        x["case_id"] for x in failures
    }
    for _, r in test[test.case_id.isin(ids)].iterrows():
        case_rows.append(
            {
                "case_id": r.case_id,
                "placed": str(r.placed),
                "label": int(r.target),
                "probability": float(r.probability),
                "features": {
                    k: (float(r[k]) if k in BASE_NUM + HISTORY + GRAPH else str(r[k]))
                    for k in BASE_NUM + CATS + HISTORY + GRAPH
                },
                "unknown_categories": [k for k in CATS if r[k] not in set(trainf[k])],
                "evidence": [
                    "order-time planned shipping and basket metadata",
                    "matured training-only product history",
                    "past training-only structural co-occurrence degrees",
                ],
            }
        )
    dump(output / "cases.json", case_rows)
    test[["case_id", "placed", "target", "probability", "quoted_amount"]].to_csv(
        output / "test-predictions.csv", index=False
    )
    dump(
        output / "test-all-model-predictions.json",
        {k: v.tolist() for k, v in predictions.items()},
    )
    if selected in pipelines:
        joblib.dump(pipelines[selected], output / "model.joblib")
    dump(
        output / "runtime.json",
        {
            "selected": selected,
            "global_rate": global_rate,
            "threshold": champion["threshold"],
            "domain": protocol["domain"],
            "features": BASE_NUM + CATS + HISTORY + GRAPH,
            "vocab": {k: sorted(set(trainf[k])) for k in CATS},
        },
    )
    plot(output, test, p, report)
    report["elapsed_seconds"] = round(time.perf_counter() - start, 3)
    import resource

    report["peak_rss_mib"] = round(
        resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2
    )
    report["environment"] = {
        k: importlib.metadata.version(k)
        for k in [
            "numpy",
            "pandas",
            "scipy",
            "scikit-learn",
            "lightgbm",
            "joblib",
            "threadpoolctl",
            "matplotlib",
        ]
    }
    report["environment"]["python"] = platform.python_version()
    dump(output / "report.json", report)
    files = {f.name: sha(f) for f in output.iterdir() if f.is_file()}
    dump(output / "manifest.json", files)
    print(
        json.dumps(
            {
                "selected": selected,
                "validation_ap": champion["validation_ap"],
                "test_ap": report["models"][selected]["test"]["average_precision"],
                "seconds": report["elapsed_seconds"],
            }
        ),
        flush=True,
    )
    return report


def plot(output, test, p, report):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from sklearn.metrics import precision_recall_curve

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name in [
        report["selection"]["name"],
        "mature_product_history",
        "quoted_amount_ranking",
    ]:
        if name == "quoted_amount_ranking":
            score = test.quoted_amount
        elif name == "mature_product_history":
            score = test.history_rate
        else:
            score = p
        precision, recall, _ = precision_recall_curve(test.target, score)
        ax.plot(recall, precision, label=name)
    ax.axhline(
        test.target.mean(), color="gray", ls="--", label="test prevalence (reference)"
    )
    ax.set(
        xlabel="Recall",
        ylabel="Precision",
        title="DataCo chronological held-out test; AP reported separately",
    )
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(output / "precision-recall.png", dpi=160)
    fig.savefig(output / "precision-recall.svg")
    plt.close(fig)
    bins = report["models"][report["selection"]["name"]]["test"]["calibration"]
    fig, ax = plt.subplots(figsize=(5.5, 4.5))
    valid = [b for b in bins if b["count"]]
    ax.plot([0, 1], [0, 1], ls="--", color="gray")
    ax.plot(
        [b["mean_probability"] for b in valid],
        [b["observed_rate"] for b in valid],
        marker="o",
    )
    ax.set(
        xlabel="Mean predicted probability",
        ylabel="Observed late rate",
        title="Held-out test calibration",
        xlim=(0, 1),
        ylim=(0, 1),
    )
    fig.tight_layout()
    fig.savefig(output / "calibration.png", dpi=160)
    fig.savefig(output / "calibration.svg")
    plt.close(fig)
