"""Lightweight trace summary metrics."""

from __future__ import annotations

from typing import Any


def build_trace_summary(
    *,
    timeline: list[dict[str, Any]],
    token_usage: dict[str, Any] | None,
    retrieval_count: int,
    permission_denied_count: int,
    error_count: int,
) -> dict[str, Any]:
    latencies = [int(item.get("latency_ms") or 0) for item in timeline if item.get("latency_ms")]
    total_latency = sum(latencies) if latencies else 0
    usage = token_usage or {}
    return {
        "total_latency_ms": total_latency,
        "total_tokens": int(usage.get("total_tokens") or 0),
        "prompt_tokens": int(usage.get("prompt_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or 0),
        "estimated_cost": float(usage.get("estimated_cost") or 0),
        "model": usage.get("model"),
        "retrieval_count": retrieval_count,
        "permission_denied_count": permission_denied_count,
        "error_count": error_count,
        "node_count": len(timeline),
    }
