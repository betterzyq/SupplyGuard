"""RAG benchmark execution (deterministic retrieval metrics)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.benchmarks.dataset import EvalQuestion
from packages.benchmarks.evaluators import evaluate_rag_row, resolve_gold_chunk_ids, retrieve_naive_chunks
from packages.rag.retriever import load_chunk_contents, retrieve_authorized_chunks


async def run_rag_benchmark_item(
    session: AsyncSession,
    user_context: UserContext,
    question: EvalQuestion,
    *,
    mode: str,
    top_k: int,
    chunk_size: int,
    permission_filter: bool,
) -> dict[str, Any]:
    unsafe_baseline = not permission_filter or mode == "naive_rag"
    try:
        if unsafe_baseline:
            chunks, latency_ms = await retrieve_naive_chunks(user_context, question.question, top_k=top_k)
            filter_applied: dict[str, Any] = {"unsafe_baseline": True}
        else:
            chunks, filter_applied, latency_ms = await retrieve_authorized_chunks(
                user_context,
                question.question,
                top_k=top_k,
                chunk_size_config=chunk_size,
            )
        chunks = await load_chunk_contents(session, chunks)
        retrieved_ids = [str(item.chunk_id) for item in chunks]
        gold_chunk_ids = question.gold_chunks or await resolve_gold_chunk_ids(
            session, user_context.tenant_id, question.gold_docs
        )
        citations = [
            {
                "chunk_id": str(item.chunk_id),
                "document_id": str(item.document_id),
                "chunk_index": item.chunk_index,
                "title": item.title,
                "score": item.score,
            }
            for item in chunks
        ]
        if not chunks or question.should_be_blocked:
            answer = "未找到足够证据。"
        else:
            answer = f"Retrieved {len(chunks)} authorized chunks for benchmark."
        metrics = evaluate_rag_row(
            question,
            retrieved_ids=retrieved_ids,
            citations=citations,
            gold_chunk_ids=gold_chunk_ids,
            top_k=top_k,
            permission_filter_enabled=not unsafe_baseline,
            answer=answer,
            should_be_blocked=question.should_be_blocked,
        )
        metrics["unsafe_baseline"] = unsafe_baseline
        metrics["failure"] = False
        return {
            "predicted_answer": answer,
            "metrics": metrics,
            "latency_ms": latency_ms,
            "token_usage": {},
            "token_usage_total": 0,
            "retrieved_ids": retrieved_ids,
            "citations": citations,
            "graph_paths": [],
            "memory_used": [],
            "error": None,
            "filter_applied": filter_applied,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "predicted_answer": None,
            "metrics": {"failure": True, "recall_at_k": 0.0, "precision_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0},
            "latency_ms": 0,
            "token_usage": {},
            "token_usage_total": 0,
            "retrieved_ids": [],
            "citations": [],
            "graph_paths": [],
            "memory_used": [],
            "error": str(exc),
            "filter_applied": {},
        }
