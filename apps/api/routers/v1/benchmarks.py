"""Benchmark admin routes."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import require_admin
from apps.api.schemas.benchmark import (
    BenchmarkReportResponse,
    BenchmarkResultItem,
    BenchmarkRunListItem,
    BenchmarkRunRequest,
    BenchmarkRunResponse,
)
from packages.authz.rbac import UserContext
from packages.benchmarks.benchmark_repo import create_benchmark_run, get_benchmark_run, list_benchmark_results, list_benchmark_runs
from packages.benchmarks.benchmark_runner import BenchmarkConfig, run_benchmark
from packages.benchmarks.benchmark_tasks import schedule_benchmark_run
from packages.benchmarks.report_generator import reports_dir
from packages.common.db.session import get_db_session
from packages.observability.tracing import begin_http_trace
from packages.observability.trace_context import set_trace_id

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


@router.post("/run", response_model=BenchmarkRunResponse)
async def run_benchmark_api(
    payload: BenchmarkRunRequest,
    request: Request,
    admin_context: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> BenchmarkRunResponse:
    if payload.mode == "naive_rag" or not payload.config.permission_filter:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unsafe_baseline modes are not exposed via API",
        )
    trace_id = await begin_http_trace(
        session,
        user_context=admin_context,
        method=request.method,
        path=str(request.url.path),
        trace_id_header=request.headers.get("X-Trace-Id"),
    )
    set_trace_id(trace_id)
    request.state.trace_id = trace_id

    config = BenchmarkConfig.from_dict(
        {
            "name": payload.name,
            "mode": payload.mode,
            "limit": payload.limit,
            "dry_run": payload.dry_run,
            "config": payload.config.model_dump(),
        }
    )

    if payload.dry_run:
        result = await run_benchmark(session, admin_context=admin_context, config=config)
        await session.commit()
        return BenchmarkRunResponse(
            benchmark_run_id=result.get("benchmark_run_id"),
            trace_id=result.get("trace_id"),
            status=result["status"],
            summary=result.get("summary") or {},
        )

    target_run = await create_benchmark_run(
        session,
        tenant_id=admin_context.tenant_id,
        user_id=admin_context.user_id,
        name=config.name,
        mode=config.mode,
        config={
            "top_k": config.top_k,
            "chunk_size": config.chunk_size,
            "permission_filter": config.permission_filter,
            "memory": config.memory,
            "limit": config.limit,
        },
        trace_id=trace_id,
    )
    run_id = target_run.id
    await session.commit()

    schedule_benchmark_run(
        run_id=run_id,
        admin_context=admin_context,
        config=config,
        trace_id=trace_id,
    )

    return BenchmarkRunResponse(
        benchmark_run_id=run_id,
        trace_id=trace_id,
        status="running",
        summary={},
    )


@router.get("/runs", response_model=list[BenchmarkRunListItem])
async def list_runs(
    admin_context: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
    limit: int = 50,
) -> list[BenchmarkRunListItem]:
    runs = await list_benchmark_runs(session, admin_context.tenant_id, limit=limit)
    return [
        BenchmarkRunListItem(
            id=run.id,
            name=run.name,
            mode=run.mode,
            status=run.status,
            summary=run.summary,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )
        for run in runs
    ]


@router.get("/runs/{run_id}", response_model=BenchmarkRunListItem)
async def get_run(
    run_id: UUID,
    admin_context: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> BenchmarkRunListItem:
    run = await get_benchmark_run(session, run_id)
    if run is None or run.tenant_id != admin_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="benchmark run not found")
    return BenchmarkRunListItem(
        id=run.id,
        name=run.name,
        mode=run.mode,
        status=run.status,
        summary=run.summary,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


@router.get("/runs/{run_id}/results", response_model=list[BenchmarkResultItem])
async def get_run_results(
    run_id: UUID,
    admin_context: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> list[BenchmarkResultItem]:
    run = await get_benchmark_run(session, run_id)
    if run is None or run.tenant_id != admin_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="benchmark run not found")
    rows = await list_benchmark_results(session, run_id)
    return [
        BenchmarkResultItem(
            id=row.id,
            question_id=row.question_id,
            question_type=row.question_type,
            question=row.question,
            metrics=row.metrics,
            latency_ms=row.latency_ms,
            error=row.error,
        )
        for row in rows
    ]


@router.get("/runs/{run_id}/report", response_model=BenchmarkReportResponse)
async def get_run_report(
    run_id: UUID,
    admin_context: UserContext = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> BenchmarkReportResponse:
    run = await get_benchmark_run(session, run_id)
    if run is None or run.tenant_id != admin_context.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="benchmark run not found")
    base = reports_dir() / str(run_id)
    return BenchmarkReportResponse(
        benchmark_run_id=run_id,
        markdown_path=str(base.with_suffix(".md")) if base.with_suffix(".md").exists() else None,
        json_path=str(base.with_suffix(".json")) if base.with_suffix(".json").exists() else None,
        csv_path=str(base.with_suffix(".csv")) if base.with_suffix(".csv").exists() else None,
        summary=run.summary,
    )
