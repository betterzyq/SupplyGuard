import json
import numpy as np
import pandas as pd
import pytest
from packages.prediction.data import (
    add_features,
    BASE_NUM,
    CATS,
    HISTORY,
    GRAPH,
    PROTOCOL,
)
from packages.prediction.metrics import evaluate, ranking, threshold_from_validation


def sample():
    return pd.DataFrame(
        [
            dict(
                case_id="a",
                placed=pd.Timestamp("2016-01-01"),
                mature=pd.Timestamp("2016-01-10"),
                target=1,
                products=("p",),
                category="c",
                market="m",
                split="train",
            ),
            dict(
                case_id="b",
                placed=pd.Timestamp("2016-01-05"),
                mature=pd.Timestamp("2016-01-12"),
                target=0,
                products=("p",),
                category="c",
                market="m",
                split="train",
            ),
            dict(
                case_id="c",
                placed=pd.Timestamp("2016-01-11"),
                mature=pd.Timestamp("2016-01-20"),
                target=0,
                products=("p",),
                category="c",
                market="m",
                split="train",
            ),
            dict(
                case_id="d",
                placed=pd.Timestamp("2017-02-01"),
                mature=pd.Timestamp("2017-02-10"),
                target=1,
                products=("p",),
                category="c",
                market="m",
                split="validation",
            ),
            dict(
                case_id="e",
                placed=pd.Timestamp("2017-08-01"),
                mature=pd.Timestamp("2017-08-10"),
                target=1,
                products=("p",),
                category="c",
                market="m",
                split="test",
            ),
        ]
    )


def test_history_availability_and_holdout_labels_cannot_change_features():
    f = sample()
    r = add_features(f)
    assert r.history_count.tolist() == [0, 0, 1, 3, 3]
    assert r.product_market_degree.tolist() == [0, 1, 1, 1, 1]
    f.loc[f.split != "train", "target"] = 0
    changed = add_features(f)
    assert r[HISTORY + GRAPH].equals(changed[HISTORY + GRAPH])
    f.loc[1, "target"] = 1
    changed = add_features(f)
    assert changed.history_rate.iloc[1] == r.history_rate.iloc[1]
    assert changed.history_rate.iloc[2] == r.history_rate.iloc[2]  # b not mature yet


def test_same_timestamp_has_no_structural_or_label_lookahead():
    f = sample().iloc[:2].copy()
    f.loc[1, "placed"] = f.placed.iloc[0]
    r = add_features(f)
    assert r.history_count.tolist() == [0, 0]
    assert r.product_market_degree.tolist() == [0, 0]


def test_forbidden_post_outcome_and_pii_not_feature_allowlist():
    features = BASE_NUM + CATS + HISTORY + GRAPH
    assert not any(
        token in " ".join(features).lower()
        for token in [
            "actual",
            "shipped",
            "target",
            "label",
            "customer",
            "status",
            "profit",
            "latitude",
            "longitude",
            "email",
            "password",
        ]
    )
    p = json.loads(PROTOCOL.read_text())
    assert p["budget"]["training_fits"] == 8
    assert (
        pd.Timestamp(p["train_end"])
        < pd.Timestamp(p["validation_end"])
        < pd.Timestamp(p["test_end"])
    )


def test_ranking_fixed_budget_calibration_and_na():
    y = np.array([1, 0, 1, 0])
    p = np.array([0.8, 0.7, 0.3, 0.1])
    a = np.array([1, 10, 1, 10])
    r = ranking(y, p, a, 0.25)
    assert r == {
        "k": 1,
        "recall": 0.5,
        "precision": 1,
        "late_quoted_amount_capture": 0.5,
    }
    m = evaluate(y, p, a, 0.5)
    assert m["confusion"] == {"tp": 1, "fp": 1, "tn": 1, "fn": 1}
    assert sum(x["count"] for x in m["calibration"]) == 4
    assert "brier" not in evaluate(y, a, a, probability=False)
    assert evaluate(np.zeros(4), p, a)["average_precision"] is None
    assert 0.05 <= threshold_from_validation(y, p) <= 0.95


def test_artifact_missing_and_integrity_fail_closed(tmp_path, monkeypatch):
    from packages.prediction import runtime

    monkeypatch.setattr(runtime, "BASE", tmp_path)
    with pytest.raises(FileNotFoundError):
        runtime.report()
    (tmp_path / "active.json").write_text(
        json.dumps({"run_id": "../../etc", "manifest_sha256": "x"})
    )
    with pytest.raises(ValueError):
        runtime.active_directory()
