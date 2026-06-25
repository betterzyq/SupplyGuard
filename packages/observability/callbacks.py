"""LangGraph node wrappers and optional LangSmith callbacks."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from packages.agents.state import AgentState
from packages.common.config import get_settings
from packages.common.logging import get_logger
from packages.observability.cost_tracker import enrich_token_usage
from packages.observability.error_tracker import record_error
from packages.observability.repositories.node_span_repo import write_node_span

logger = get_logger("observability.callbacks")

NodeFn = Callable[[AgentState], Awaitable[AgentState]]


def setup_langsmith_tracing() -> None:
    settings = get_settings()
    if not settings.LANGSMITH_TRACING or not settings.LANGSMITH_API_KEY:
        return
    try:
        import os

        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", settings.LANGSMITH_API_KEY)
        os.environ.setdefault("LANGSMITH_PROJECT", settings.LANGSMITH_PROJECT)
        logger.info("langsmith_tracing_enabled project={}", settings.LANGSMITH_PROJECT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("langsmith_setup_skipped error={}", exc)


def get_langgraph_callbacks() -> list[Any]:
    settings = get_settings()
    if not settings.LANGSMITH_TRACING or not settings.LANGSMITH_API_KEY:
        return []
    try:
        from langsmith import Client

        client = Client(api_key=settings.LANGSMITH_API_KEY)
        if not client.api_key:
            return []
        from langchain_core.tracers.langchain import LangChainTracer

        return [LangChainTracer(project_name=settings.LANGSMITH_PROJECT, client=client)]
    except Exception as exc:  # noqa: BLE001
        logger.warning("langsmith_callbacks_unavailable error={}", exc)
        return []


def wrap_agent_node(node_name: str, fn: NodeFn) -> NodeFn:
    async def wrapped(state: AgentState) -> AgentState:
        started = time.perf_counter()
        start_time = datetime.now(UTC)
        user_context = state["user_context"]
        session = state.get("db_session")
        trace_id = state["trace_id"]
        agent_run_id_raw = state.get("agent_run_id")
        agent_run_id = uuid.UUID(agent_run_id_raw) if agent_run_id_raw else None

        try:
            result = await fn(state)
            latency_ms = int((time.perf_counter() - started) * 1000)
            if session is not None:
                await write_node_span(
                    session,
                    tenant_id=user_context.tenant_id,
                    user_id=user_context.user_id,
                    trace_id=trace_id,
                    node_name=node_name,
                    start_time=start_time,
                    end_time=datetime.now(UTC),
                    latency_ms=latency_ms,
                    status="completed",
                    agent_run_id=agent_run_id,
                )
            nodes_executed = list(result.get("nodes_executed") or [])
            if node_name not in nodes_executed and not any(
                node_name in str(item) for item in nodes_executed
            ):
                nodes_executed.append(node_name)
            result["nodes_executed"] = nodes_executed
            return result
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            record_error(trace_id=trace_id, node_name=node_name, error=exc)
            if session is not None:
                await write_node_span(
                    session,
                    tenant_id=user_context.tenant_id,
                    user_id=user_context.user_id,
                    trace_id=trace_id,
                    node_name=node_name,
                    start_time=start_time,
                    end_time=datetime.now(UTC),
                    latency_ms=latency_ms,
                    status="failed",
                    error_message=str(exc),
                    agent_run_id=agent_run_id,
                )
            raise

    wrapped.__name__ = getattr(fn, "__name__", node_name)
    return wrapped


def merge_token_usage(state: AgentState, new_usage: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    existing = dict(state.get("token_usage") or {})
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        existing[key] = int(existing.get(key) or 0) + int(new_usage.get(key) or 0)
    return enrich_token_usage(existing, model=settings.DEEPSEEK_MODEL)
