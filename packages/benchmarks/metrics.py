"""Deterministic benchmark metrics (no LLM judge)."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any, Sequence


def recall_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    if not gold:
        return 1.0 if not retrieved[:k] else 0.0
    gold_set = set(gold)
    hits = len(gold_set & set(retrieved[:k]))
    return hits / len(gold_set)


def precision_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = retrieved[:k]
    if not top:
        return 0.0
    gold_set = set(gold)
    hits = sum(1 for item in top if item in gold_set)
    return hits / len(top)


def mrr(retrieved: Sequence[str], gold: Sequence[str]) -> float:
    gold_set = set(gold)
    for index, item in enumerate(retrieved, start=1):
        if item in gold_set:
            return 1.0 / index
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], gold: Sequence[str], k: int) -> float:
    if not gold:
        return 1.0
    gold_set = set(gold)
    dcg = 0.0
    for index, item in enumerate(retrieved[:k], start=1):
        if item in gold_set:
            dcg += 1.0 / math.log2(index + 1)
    ideal_hits = min(len(gold_set), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def citation_accuracy(citations: Sequence[dict[str, Any]], gold_chunk_ids: Sequence[str]) -> float:
    if not gold_chunk_ids:
        return 1.0 if not citations else 0.0
    if not citations:
        return 0.0
    cited_ids = {str(c.get("chunk_id") or c.get("id") or "") for c in citations}
    cited_ids |= {str(c.get("document_id", "")) + "#" + str(c.get("chunk_index", "")) for c in citations}
    gold_set = set(str(g) for g in gold_chunk_ids)
    hits = sum(1 for g in gold_set if any(g in cid or cid.endswith(g) for cid in cited_ids if cid))
    return hits / len(gold_set) if gold_set else 1.0


def graph_path_hit_rate(found_paths: Sequence[str], gold_paths: Sequence[Sequence[str]]) -> float:
    if not gold_paths:
        return 1.0 if not found_paths else 0.0
    if not found_paths:
        return 0.0
    hits = 0
    for gold in gold_paths:
        normalized = [node.replace("Supplier:", "Supplier ").replace(":", " ") for node in gold]
        joined = " → ".join(gold)
        if any(all(token.split(":")[-1] in path for token in gold if ":" in token) for path in found_paths):
            hits += 1
        elif any(piece in path for path in found_paths for piece in normalized):
            hits += 1
        elif any(joined in path or path in joined for path in found_paths):
            hits += 1
    return hits / len(gold_paths)


def entity_recall(found_entities: Sequence[str], gold_entities: Sequence[str]) -> float:
    if not gold_entities:
        return 1.0
    gold_set = {e.upper() for e in gold_entities}
    found_set = {e.upper() for e in found_entities}
    return len(gold_set & found_set) / len(gold_set)


def permission_violation_rate(results: list[dict[str, Any]]) -> float:
    perm = [r for r in results if r.get("requires_permission") or r.get("should_be_blocked")]
    if not perm:
        return 0.0
    violations = sum(1 for r in perm if r.get("permission_violation"))
    return violations / len(perm)


def blocked_accuracy(results: list[dict[str, Any]]) -> float:
    blocked = [r for r in results if r.get("should_be_blocked")]
    if not blocked:
        return 1.0
    correct = sum(1 for r in blocked if r.get("was_blocked_or_no_evidence"))
    return correct / len(blocked)


def allowed_accuracy(results: list[dict[str, Any]]) -> float:
    allowed = [r for r in results if not r.get("should_be_blocked") and r.get("requires_permission")]
    if not allowed:
        return 1.0
    correct = sum(1 for r in allowed if not r.get("was_blocked_or_no_evidence") and r.get("has_evidence"))
    return correct / len(allowed)


def false_block_rate(results: list[dict[str, Any]]) -> float:
    allowed = [r for r in results if not r.get("should_be_blocked")]
    if not allowed:
        return 0.0
    false_blocks = sum(1 for r in allowed if r.get("was_blocked_or_no_evidence") and r.get("expected_evidence"))
    return false_blocks / len(allowed)


def memory_hit_rate(results: list[dict[str, Any]]) -> float:
    mem = [r for r in results if r.get("requires_memory")]
    if not mem:
        return 1.0
    hits = sum(1 for r in mem if r.get("memory_hit"))
    return hits / len(mem)


def latency_percentiles(latencies: list[int]) -> dict[str, float]:
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "mean": 0.0}
    sorted_vals = sorted(latencies)
    n = len(sorted_vals)

    def pct(p: float) -> float:
        idx = min(n - 1, max(0, int(math.ceil(p * n) - 1)))
        return float(sorted_vals[idx])

    return {
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "mean": float(mean(sorted_vals)),
    }


def aggregate_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    latencies = [int(r.get("latency_ms", 0)) for r in rows]
    perc = latency_percentiles(latencies)
    failures = sum(1 for r in rows if r.get("failure"))
    return {
        "count": len(rows),
        "recall_at_k": float(mean([r.get("recall_at_k", 0) for r in rows])) if rows else 0.0,
        "precision_at_k": float(mean([r.get("precision_at_k", 0) for r in rows])) if rows else 0.0,
        "mrr": float(mean([r.get("mrr", 0) for r in rows])) if rows else 0.0,
        "ndcg_at_k": float(mean([r.get("ndcg_at_k", 0) for r in rows])) if rows else 0.0,
        "citation_accuracy": float(mean([r.get("citation_accuracy", 0) for r in rows])) if rows else 0.0,
        "graph_path_hit_rate": float(mean([r.get("graph_path_hit_rate", 0) for r in rows if r.get("graph_path_hit_rate") is not None])) if any(r.get("graph_path_hit_rate") is not None for r in rows) else None,
        "entity_recall": float(mean([r.get("entity_recall", 0) for r in rows if r.get("entity_recall") is not None])) if any(r.get("entity_recall") is not None for r in rows) else None,
        "permission_violation_rate": permission_violation_rate(rows),
        "blocked_accuracy": blocked_accuracy(rows),
        "allowed_accuracy": allowed_accuracy(rows),
        "false_block_rate": false_block_rate(rows),
        "memory_hit_rate": memory_hit_rate(rows),
        "latency_ms": perc["mean"],
        "p50_latency_ms": perc["p50"],
        "p95_latency_ms": perc["p95"],
        "p99_latency_ms": perc["p99"],
        "token_usage_total": sum(int(r.get("token_usage_total", 0) or 0) for r in rows),
        "failure_rate": failures / len(rows),
        "unsafe_retrieval_count": sum(1 for r in rows if r.get("unsafe_retrieval")),
    }
