"""Error capture helpers for observability."""

from __future__ import annotations

from typing import Any

from packages.common.logging import get_logger

logger = get_logger("observability.error_tracker")


def record_error(
    *,
    trace_id: str | None,
    node_name: str | None,
    error: Exception | str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message = str(error)
    payload = {
        "trace_id": trace_id,
        "node_name": node_name,
        "error_message": message,
        "context": context or {},
    }
    logger.error(
        "trace_error trace_id={} node={} error={}",
        trace_id,
        node_name,
        message,
    )
    return payload
