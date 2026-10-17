"""Strict scorer-v2. None means not evaluable; absence is never a perfect score."""

from __future__ import annotations
import math
import re
from statistics import mean
from typing import Any, Sequence

SCORER_VERSION = "enterprise-scorer-v2"


def unique(items):
    return list(dict.fromkeys(items))


def recall_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int):
    return (
        len(set(retrieved[: max(0, k)]) & set(gold)) / len(set(gold)) if gold else None
    )


def precision_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int):
    if not gold:
        return None
    # k result slots, duplicates occupy slots without repeated credit; no padding denominator.
    top = list(retrieved[: max(0, k)])
    return len(set(top) & set(gold)) / len(top) if top else 0.0


def mrr(retrieved: Sequence[str], gold: Sequence[str]):
    if not gold:
        return None
    return next((1 / i for i, x in enumerate(retrieved, 1) if x in set(gold)), 0.0)


def ndcg_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int):
    if not gold:
        return None
    seen = set()
    dcg = 0.0
    for i, x in enumerate(retrieved[: max(0, k)], 1):
        if x in set(gold) and x not in seen:
            dcg += 1 / math.log2(i + 1)
        seen.add(x)
    ideal = sum(
        1 / math.log2(i + 1) for i in range(1, min(len(set(gold)), max(0, k)) + 1)
    )
    return dcg / ideal if ideal else 0.0


def citation_scores(citations: Sequence[dict[str, Any]], gold_chunk_ids: Sequence[str]):
    if not gold_chunk_ids:
        return {"citation_precision": None, "citation_recall": None}
    # Chunk UUID takes precedence. doc#index accepted only when no chunk identifier exists.
    cited = {
        str(
            c.get("chunk_id")
            or c.get("id")
            or (
                str(c["document_id"]) + "#" + str(c["chunk_index"])
                if c.get("document_id") is not None and c.get("chunk_index") is not None
                else "__missing_identity_" + str(index)
            )
        )
        for index, c in enumerate(citations)
    }
    cited.discard("")
    gold = set(map(str, gold_chunk_ids))
    hit = len(cited & gold)
    return {
        "citation_precision": hit / len(cited) if cited else 0.0,
        "citation_recall": hit / len(gold),
    }


def citation_accuracy(citations, gold_chunk_ids):
    """Deprecated name retained for API compatibility; v2 means exact precision."""
    return citation_scores(citations, gold_chunk_ids)["citation_precision"]


def path_nodes(path):
    text = " → ".join(path) if not isinstance(path, str) else path
    # Full typed nodes only. Relationship names cannot match a node.
    return [
        (a.lower(), b.upper())
        for a, b in re.findall(
            r"\b(Supplier|Material|Product|Order|Customer|RiskEvent|DeliveryEvent|QualityIssue)\s*[: ]\s*([A-Za-z0-9]+(?:-[A-Za-z0-9]+)*)\b",
            text,
            re.I,
        )
    ]


def graph_path_hit_rate(found_paths, gold_paths):
    if not gold_paths:
        return None
    expected = [path_nodes(p) for p in gold_paths]
    observed = [path_nodes(p) for p in found_paths]
    # Exact complete ordered typed sequence: no prefixes, reversal or partial-path credit.
    return sum(bool(g) and g in observed for g in expected) / len(expected)


def entity_recall(found_entities, gold_entities):
    if not gold_entities:
        return None
    gold = {e.upper() for e in gold_entities}
    return len(gold & {e.upper() for e in found_entities}) / len(gold)


def _rate(rows, predicate):
    return sum(bool(predicate(r)) for r in rows) / len(rows) if rows else None


def permission_violation_rate(results):
    rows = [
        r
        for r in results
        if r.get("requires_permission") and r.get("permission_violation") is not None
    ]
    return _rate(rows, lambda r: r["permission_violation"])


def blocked_accuracy(results):
    rows = [r for r in results if r.get("should_be_blocked")]
    return _rate(rows, lambda r: r.get("decision") == "denied")


def allowed_accuracy(results):
    rows = [
        r
        for r in results
        if not r.get("should_be_blocked") and r.get("requires_permission")
    ]
    # Access decision, not successful retrieval quality. No-evidence stays separate.
    return _rate(rows, lambda r: r.get("decision") in {"allow", "no_evidence"})


def false_block_rate(results):
    rows = [
        r
        for r in results
        if not r.get("should_be_blocked") and r.get("requires_permission")
    ]
    return _rate(rows, lambda r: r.get("decision") == "denied")


def memory_hit_rate(results):
    return _rate(
        [r for r in results if r.get("requires_memory")], lambda r: r.get("memory_hit")
    )


def latency_percentiles(latencies):
    if not latencies:
        return {k: None for k in ["p50", "p95", "p99", "mean"]}
    vals = sorted(latencies)
    return {
        **{
            k: float(vals[min(len(vals) - 1, max(0, math.ceil(p * len(vals)) - 1))])
            for k, p in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99)]
        },
        "mean": float(mean(vals)),
    }


def aggregate_metrics(rows):
    if not rows:
        return {}
    keys = [
        "recall_at_k",
        "precision_at_k",
        "mrr",
        "ndcg_at_k",
        "citation_accuracy",
        "citation_precision",
        "citation_recall",
        "graph_path_hit_rate",
        "entity_recall",
    ]
    result = {
        "scorer_version": SCORER_VERSION,
        "count": len(rows),
        "metric_denominators": {},
    }
    for key in keys:
        vals = [r[key] for r in rows if r.get(key) is not None]
        result[key] = float(mean(vals)) if vals else None
        result["metric_denominators"][key] = len(vals)
    result.update(
        permission_violation_rate=permission_violation_rate(rows),
        blocked_accuracy=blocked_accuracy(rows),
        allowed_accuracy=allowed_accuracy(rows),
        false_block_rate=false_block_rate(rows),
        memory_hit_rate=memory_hit_rate(rows),
    )
    perc = latency_percentiles(
        [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    )
    result.update(
        latency_ms=perc["mean"],
        p50_latency_ms=perc["p50"],
        p95_latency_ms=perc["p95"],
        p99_latency_ms=perc["p99"],
        token_usage_total=sum(int(r.get("token_usage_total", 0) or 0) for r in rows),
        failure_rate=sum(bool(r.get("failure")) for r in rows) / len(rows),
        unsafe_retrieval_count=sum(bool(r.get("unsafe_retrieval")) for r in rows),
        decision_counts={
            d: sum(r.get("decision") == d for r in rows)
            for d in ["allow", "denied", "no_evidence", "error"]
        },
    )
    return result
