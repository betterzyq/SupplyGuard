"""Order-level metrics; AP is sklearn average precision, never trapezoidal PR area."""

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)


def ranking(y, scores, amount, fraction):
    k = max(1, int(np.ceil(len(y) * fraction)))
    top = np.argsort(-np.asarray(scores), kind="stable")[:k]
    total = float(np.dot(y, amount))
    return {
        "k": k,
        "recall": float(np.sum(y[top]) / np.sum(y)) if np.sum(y) else None,
        "precision": float(np.mean(y[top])),
        "late_quoted_amount_capture": (
            float(np.dot(y[top], amount[top]) / total) if total else None
        ),
    }


def evaluate(y, scores, amount, threshold=None, probability=True):
    y, scores, amount = np.asarray(y), np.asarray(scores), np.asarray(amount)
    if len(y) == 0:
        return {"count": 0, "average_precision": None}
    both = len(np.unique(y)) == 2
    result = {
        "count": len(y),
        "positive_rate": float(y.mean()),
        "average_precision": (
            float(average_precision_score(y, scores)) if both else None
        ),
        "roc_auc": float(roc_auc_score(y, scores)) if both else None,
        "ranking": {
            str(int(f * 100)): ranking(y, scores, amount, f) for f in [0.05, 0.1, 0.2]
        },
    }
    if probability:
        result["brier"] = float(brier_score_loss(y, scores))
        bins = []
        for i in range(10):
            mask = (scores >= i / 10) & (
                (scores < (i + 1) / 10) if i < 9 else scores <= 1
            )
            bins.append(
                {
                    "lower": i / 10,
                    "count": int(mask.sum()),
                    "mean_probability": (
                        float(scores[mask].mean()) if mask.any() else None
                    ),
                    "observed_rate": float(y[mask].mean()) if mask.any() else None,
                }
            )
        result["calibration"] = bins
        result["ece"] = float(
            sum(
                b["count"] * abs(b["mean_probability"] - b["observed_rate"])
                for b in bins
                if b["count"]
            )
            / len(y)
        )
        if threshold is not None:
            pred = scores >= threshold
            p, r, f, _ = precision_recall_fscore_support(
                y, pred, average="binary", zero_division=0
            )
            result.update(
                threshold=float(threshold),
                precision=float(p),
                recall=float(r),
                f1=float(f),
                confusion={
                    "tp": int((pred & (y == 1)).sum()),
                    "fp": int((pred & (y == 0)).sum()),
                    "tn": int((~pred & (y == 0)).sum()),
                    "fn": int((~pred & (y == 1)).sum()),
                },
            )
    return result


def threshold_from_validation(y, p):
    from sklearn.metrics import f1_score

    candidates = np.arange(1, 20) / 20
    return float(max(candidates, key=lambda t: f1_score(y, p >= t, zero_division=0)))


def bootstrap(
    frame, scores, comparator, seed, repetitions=200, additional_comparators=None
):
    """Resample calendar weeks to preserve within-week order correlation."""
    y = frame.target.to_numpy()
    weeks = frame.placed.dt.to_period("W").astype(str).to_numpy()
    blocks = [np.flatnonzero(weeks == w) for w in sorted(set(weeks))]
    rng = np.random.default_rng(seed)
    samples = {
        k: []
        for k in ["average_precision", "recall_at_10", "brier", "ap_delta_vs_amount"]
    }
    for name in additional_comparators or {}:
        samples["ap_delta_vs_" + name] = []
    for _ in range(repetitions):
        idx = np.concatenate(
            [blocks[i] for i in rng.integers(0, len(blocks), len(blocks))]
        )
        yy, pp = y[idx], scores[idx]
        if len(np.unique(yy)) < 2:
            continue
        ap = float(average_precision_score(yy, pp))
        samples["average_precision"].append(ap)
        samples["recall_at_10"].append(ranking(yy, pp, np.ones(len(yy)), 0.1)["recall"])
        samples["brier"].append(float(brier_score_loss(yy, pp)))
        samples["ap_delta_vs_amount"].append(
            ap - float(average_precision_score(yy, comparator[idx]))
        )
        for name, reference in (additional_comparators or {}).items():
            samples["ap_delta_vs_" + name].append(
                ap - float(average_precision_score(yy, reference[idx]))
            )
    return {
        "method": "calendar-week block bootstrap; paired AP delta; percentile 95%",
        "blocks": len(blocks),
        "resamples": repetitions,
        "intervals": {
            k: {
                "low": float(np.quantile(v, 0.025)),
                "high": float(np.quantile(v, 0.975)),
                "valid_resamples": len(v),
            }
            for k, v in samples.items()
        },
    }
