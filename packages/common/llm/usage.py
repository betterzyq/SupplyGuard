"""Token usage normalization and cost estimation."""

from __future__ import annotations

from typing import Any

from packages.observability.cost_tracker import enrich_token_usage, estimate_cost as _estimate_cost

__all__ = ["normalize_token_usage", "estimate_cost", "enrich_token_usage"]


def normalize_token_usage(raw: Any | None) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        usage = dict(raw)
    else:
        usage = {
            "prompt_tokens": getattr(raw, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(raw, "completion_tokens", 0) or 0,
            "total_tokens": getattr(raw, "total_tokens", 0) or 0,
        }
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    total = int(usage.get("total_tokens") or 0)
    if total == 0:
        total = prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def estimate_cost(token_usage: dict[str, Any] | None, *, model: str | None = None) -> float:
    return _estimate_cost(token_usage, model=model)
