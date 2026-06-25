"""Latency aggregation helpers."""

from __future__ import annotations

from packages.benchmarks.metrics import latency_percentiles


def summarize_latency(rows: list[dict]) -> dict:
    latencies = [int(r.get("latency_ms", 0)) for r in rows]
    return latency_percentiles(latencies)
