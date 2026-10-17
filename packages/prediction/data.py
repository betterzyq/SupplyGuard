"""Order-grain DataCo preparation. Outcome fields never enter model features."""

from __future__ import annotations

import hashlib
import heapq
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/catalog/prediction-protocol-v1.json"
SAFE_COLUMNS = [
    "Order Id",
    "Order Item Id",
    "order date (DateOrders)",
    "shipping date (DateOrders)",
    "Days for shipping (real)",
    "Days for shipment (scheduled)",
    "Late_delivery_risk",
    "Order Status",
    "Shipping Mode",
    "Order Item Quantity",
    "Order Item Product Price",
    "Order Item Discount Rate",
    "Product Card Id",
    "Category Name",
    "Market",
    "Order Region",
    "Order Country",
    "Latitude",
    "Longitude",
]
BASE_NUM = [
    "planned_min",
    "planned_max",
    "item_count",
    "quantity",
    "quoted_amount",
    "price_mean",
    "discount_mean",
    "month",
    "weekday",
    "hour",
    "product_count",
]
CATS = ["mode", "market", "region", "country", "category"]
HISTORY = ["history_rate", "history_count"]
GRAPH = ["product_market_degree", "category_product_degree", "market_product_degree"]


def case_id(order_id):
    return hashlib.sha256(("dataco-v5:" + str(int(order_id))).encode()).hexdigest()[:20]


def prepare(raw: Path):
    protocol = json.loads(PROTOCOL.read_text())
    f = pd.read_csv(raw, encoding="latin1", usecols=SAFE_COLUMNS)
    audit = {
        "raw_items": len(f),
        "raw_orders": int(f["Order Id"].nunique()),
        "duplicate_item_ids": int(f["Order Item Id"].duplicated().sum()),
        "invalid_coordinates_items": int(
            (~f.Latitude.between(-90, 90) | ~f.Longitude.between(-180, 180)).sum()
        ),
        "missing_by_safe_column": {k: int(v) for k, v in f.isna().sum().items()},
        "pii_policy": "Only explicit safe columns read; no customer identifiers/names/email/address/password retained. Coordinates audited, never features.",
    }
    if audit["duplicate_item_ids"]:
        raise ValueError(
            "Duplicate item IDs require audit; refusing silent deduplication"
        )
    f["placed"] = pd.to_datetime(
        f["order date (DateOrders)"], format="mixed", errors="coerce"
    )
    f["shipped"] = pd.to_datetime(
        f["shipping date (DateOrders)"], format="mixed", errors="coerce"
    )
    actual, planned = f["Days for shipping (real)"], f["Days for shipment (scheduled)"]
    f["target"] = (actual > planned).astype(int)
    mismatch = f["target"] != f["Late_delivery_risk"]
    audit["label_mismatch_items_by_status"] = {
        str(k): int(v)
        for k, v in f.loc[mismatch, "Order Status"].value_counts().items()
    }
    cancelled = set(
        f.loc[f["Order Status"].isin(protocol["exclude_status"]), "Order Id"]
    )
    malformed = (
        f.placed.isna()
        | f.shipped.isna()
        | (f.shipped < f.placed)
        | (actual < 0)
        | (planned < 0)
        | ~np.isfinite(actual)
        | ~np.isfinite(planned)
    )
    invalid = set(f.loc[malformed, "Order Id"])
    inconsistent = f.groupby("Order Id").agg(
        times=("placed", "nunique"), labels=("target", "nunique")
    )
    invalid.update(
        inconsistent.index[(inconsistent.times != 1) | (inconsistent.labels != 1)]
    )
    invalid.update(f.loc[mismatch & ~f["Order Id"].isin(cancelled), "Order Id"])
    audit["excluded_cancel_fraud_orders"] = len(cancelled)
    audit["excluded_other_invalid_orders"] = len(invalid - cancelled)
    f = f[~f["Order Id"].isin(cancelled | invalid)].copy()
    f["mature"] = pd.concat(
        [
            f.shipped,
            f.placed + pd.to_timedelta(f["Days for shipping (real)"], unit="D"),
        ],
        axis=1,
    ).max(axis=1) + pd.Timedelta(days=7)
    f["quoted"] = (
        f["Order Item Quantity"]
        * f["Order Item Product Price"]
        * (1 - f["Order Item Discount Rate"])
    )
    rows = []

    def one(series):
        values = sorted(set(series.fillna("unknown").astype(str)))
        return values[0] if len(values) == 1 else "__mixed__"

    for oid, g in f.groupby("Order Id", sort=False):
        t = g.placed.iloc[0]
        rows.append(
            dict(
                case_id=case_id(oid),
                placed=t,
                mature=g.mature.max(),
                target=int(g.target.max()),
                products=tuple(sorted(set(g["Product Card Id"].astype(str)))),
                planned_min=float(g["Days for shipment (scheduled)"].min()),
                planned_max=float(g["Days for shipment (scheduled)"].max()),
                item_count=len(g),
                quantity=float(g["Order Item Quantity"].sum()),
                quoted_amount=float(g.quoted.sum()),
                price_mean=float(g["Order Item Product Price"].mean()),
                discount_mean=float(g["Order Item Discount Rate"].mean()),
                month=t.month,
                weekday=t.weekday(),
                hour=t.hour,
                product_count=g["Product Card Id"].nunique(),
                mode=one(g["Shipping Mode"]),
                market=one(g.Market),
                region=one(g["Order Region"]),
                country=one(g["Order Country"]),
                category=one(g["Category Name"]),
            )
        )
    orders = (
        pd.DataFrame(rows).sort_values(["placed", "case_id"]).reset_index(drop=True)
    )
    orders["split"] = "excluded"
    for name, start, end, available in [
        ("train", None, protocol["train_end"], protocol["train_end"]),
        (
            "validation",
            protocol["train_end"],
            protocol["validation_end"],
            protocol["validation_end"],
        ),
        (
            "test",
            protocol["validation_end"],
            protocol["test_end"],
            protocol["audit_end"],
        ),
    ]:
        mask = (orders.placed < pd.Timestamp(end)) & (
            orders.mature < pd.Timestamp(available)
        )
        if start:
            mask &= orders.placed >= pd.Timestamp(start)
        orders.loc[mask, "split"] = name
    audit.update(
        eligible_orders=len(orders),
        split_counts={k: int(v) for k, v in orders.split.value_counts().items()},
        date_min=str(orders.placed.min()),
        date_max=str(orders.placed.max()),
        same_order_overlap=0,
        maturity_lag_days=7,
    )
    return orders, audit


def add_features(orders):
    """Heap releases only mature training outcomes; graph edges group by placed time."""
    result = orders.copy()
    totals = defaultdict(lambda: [0, 0])
    global_total = [0, 0]
    pending = []
    pm, cp, mp = defaultdict(set), defaultdict(set), defaultdict(set)
    values = {}
    frozen = False
    cut = pd.Timestamp(json.loads(PROTOCOL.read_text())["train_end"])

    def release(t):
        while pending and pending[0][0] < t:
            _, _, products, label = heapq.heappop(pending)
            global_total[0] += label
            global_total[1] += 1
            for p in products:
                totals[p][0] += label
                totals[p][1] += 1

    for t, group in result.groupby("placed", sort=True):
        if t >= cut and not frozen:
            release(cut)
            frozen = True
        if not frozen:
            release(t)
        for i, r in group.iterrows():
            # A fixed Beta(1,1) prior before any outcome, otherwise mature global rate.
            prior = (global_total[0] + 1) / (global_total[1] + 2)
            rates = [
                (totals[p][0] + 10 * prior) / (totals[p][1] + 10) for p in r.products
            ]
            values[i] = [
                float(np.mean(rates)),
                float(sum(totals[p][1] for p in r.products)),
                float(np.mean([len(pm[p]) for p in r.products])),
                float(len(cp[r.category])),
                float(len(mp[r.market])),
            ]
        # Identical timestamps cannot see each other's labels or edges.
        if not frozen:
            for i, r in group[group.split == "train"].iterrows():
                heapq.heappush(pending, (r.mature, i, r.products, int(r.target)))
                for p in r.products:
                    pm[p].add(r.market)
                    cp[r.category].add(p)
                    mp[r.market].add(p)
    result[HISTORY + GRAPH] = (
        pd.DataFrame.from_dict(values, orient="index").reindex(result.index).values
    )
    return result


def split_manifest(orders):
    return {
        name: {
            "count": len(g),
            "positive_rate": float(g.target.mean()),
            "min_time": str(g.placed.min()),
            "max_time": str(g.placed.max()),
            "ids_sha256": hashlib.sha256(
                "\n".join(sorted(g.case_id)).encode()
            ).hexdigest(),
        }
        for name, g in orders[orders.split != "excluded"].groupby("split")
    }
