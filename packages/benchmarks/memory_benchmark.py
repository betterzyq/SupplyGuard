"""Memory benchmark execution."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.benchmarks.dataset import EvalQuestion
from packages.benchmarks.evaluators import evaluate_memory_row
from packages.memory.memory_retriever import retrieve_memory_evidence
from packages.memory.memory_types import SessionMessage
from packages.memory.short_term import append_message, now_iso


async def run_memory_benchmark_item(
    session: AsyncSession,
    user_context: UserContext,
    question: EvalQuestion,
) -> dict[str, Any]:
    session_id = question.follow_up_session_id or f"bench-{question.id}"
    try:
        for seed in question.session_seed:
            await append_message(
                str(user_context.tenant_id),
                str(user_context.user_id),
                session_id,
                SessionMessage(
                    role=str(seed.get("role", "user")),
                    content=str(seed.get("content", "")),
                    timestamp=now_iso(),
                    entities={
                        k: str(v) for k, v in (seed.get("entities") or {}).items()
                    },
                ),
            )

        started = __import__("time").perf_counter()
        memory_evidence, _ = await retrieve_memory_evidence(
            session,
            user_context,
            question.question,
            session_id=session_id,
        )
        latency_ms = int((__import__("time").perf_counter() - started) * 1000)
        answer = (
            memory_evidence[0]["content"] if memory_evidence else "未找到足够证据。"
        )
        memory_metrics = evaluate_memory_row(
            question,
            memory_used=memory_evidence,
            answer=answer,
            session_hit=False,
        )
        memory_metrics["failure"] = False
        memory_metrics["latency_ms"] = latency_ms

        return {
            "predicted_answer": answer,
            "metrics": memory_metrics,
            "latency_ms": latency_ms,
            "token_usage": {},
            "token_usage_total": 0,
            "retrieved_ids": [],
            "citations": [],
            "graph_paths": [],
            "memory_used": memory_evidence,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "predicted_answer": None,
            "metrics": {
                "memory_hit": False,
                "follow_up_success": False,
                "wrong_memory_rate": 0.0,
                "failure": True,
            },
            "latency_ms": 0,
            "token_usage": {},
            "token_usage_total": 0,
            "retrieved_ids": [],
            "citations": [],
            "graph_paths": [],
            "memory_used": [],
            "error": str(exc),
        }
