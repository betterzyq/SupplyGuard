"""LLM cost estimation (deterministic, no external billing API)."""

from __future__ import annotations

from typing import Any

# USD per 1M tokens (approximate DeepSeek chat pricing placeholders)
MODEL_COSTS: dict[str, dict[str, float]] = {
    "deepseek-chat": {"prompt": 0.27, "completion": 1.10},
    "deepseek-reasoner": {"prompt": 0.55, "completion": 2.19},
    "deepseek-v4-flash": {"prompt": 0.27, "completion": 1.10},
    "default": {"prompt": 0.50, "completion": 1.50},
}


def estimate_cost(
    token_usage: dict[str, Any] | None,
    *,
    model: str | None = None,
) -> float:
    if not token_usage:
        return 0.0
    rates = MODEL_COSTS.get(model or "default", MODEL_COSTS["default"])
    prompt_tokens = float(token_usage.get("prompt_tokens") or 0)
    completion_tokens = float(token_usage.get("completion_tokens") or 0)
    cost = (prompt_tokens * rates["prompt"] + completion_tokens * rates["completion"]) / 1_000_000
    return round(cost, 8)


def enrich_token_usage(
    token_usage: dict[str, Any] | None,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    usage = dict(token_usage or {})
    usage["model"] = model
    usage["estimated_cost"] = estimate_cost(usage, model=model)
    return usage
