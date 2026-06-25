"""Benchmark result persistence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.benchmark import BenchmarkResult, BenchmarkRun


async def create_benchmark_run(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    mode: str,
    config: dict[str, Any],
    dataset_name: str = "supplyguard_eval",
    trace_id: str | None = None,
) -> BenchmarkRun:
    run = BenchmarkRun(
        tenant_id=tenant_id,
        user_id=user_id,
        name=name,
        mode=mode,
        dataset_name=dataset_name,
        config=config,
        status="running",
        summary={},
        trace_id=trace_id,
    )
    session.add(run)
    await session.flush()
    return run


async def finalize_benchmark_run(
    session: AsyncSession,
    run: BenchmarkRun,
    *,
    status: str,
    summary: dict[str, Any],
    error_message: str | None = None,
) -> BenchmarkRun:
    run.status = status
    run.summary = summary
    run.completed_at = datetime.now(UTC)
    run.error_message = error_message
    await session.flush()
    return run


async def add_benchmark_result(
    session: AsyncSession,
    *,
    benchmark_run_id: uuid.UUID,
    question_id: str,
    question: str,
    question_type: str,
    ground_truth: dict[str, Any],
    predicted_answer: str | None,
    metrics: dict[str, Any],
    latency_ms: int,
    token_usage: dict[str, Any],
    retrieved_ids: list[str],
    citations: list[dict],
    graph_paths: list[dict],
    memory_used: list[dict],
    error: str | None = None,
    trace_id: str | None = None,
) -> BenchmarkResult:
    row = BenchmarkResult(
        benchmark_run_id=benchmark_run_id,
        question_id=question_id,
        question=question,
        question_type=question_type,
        ground_truth=ground_truth,
        predicted_answer=predicted_answer,
        metrics=metrics,
        latency_ms=latency_ms,
        token_usage=token_usage,
        retrieved_ids=retrieved_ids,
        citations=citations,
        graph_paths=graph_paths,
        memory_used=memory_used,
        error=error,
        trace_id=trace_id,
    )
    session.add(row)
    await session.flush()
    return row


async def get_benchmark_run(session: AsyncSession, run_id: uuid.UUID) -> BenchmarkRun | None:
    return (await session.execute(select(BenchmarkRun).where(BenchmarkRun.id == run_id))).scalar_one_or_none()


async def list_benchmark_runs(session: AsyncSession, tenant_id: uuid.UUID, *, limit: int = 50) -> list[BenchmarkRun]:
    stmt = (
        select(BenchmarkRun)
        .where(BenchmarkRun.tenant_id == tenant_id)
        .order_by(BenchmarkRun.started_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_benchmark_results(session: AsyncSession, run_id: uuid.UUID) -> list[BenchmarkResult]:
    stmt = select(BenchmarkResult).where(BenchmarkResult.benchmark_run_id == run_id)
    return list((await session.execute(stmt)).scalars().all())
