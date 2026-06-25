"""Benchmark orchestration."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from packages.authz.rbac import UserContext, build_user_context
from packages.benchmarks.benchmark_repo import (
    add_benchmark_result,
    create_benchmark_run,
    finalize_benchmark_run,
    get_benchmark_run,
    list_benchmark_results,
)
from packages.benchmarks.dataset import EvalQuestion, default_dataset_path, filter_questions, load_dataset
from packages.benchmarks.evaluators import ROLE_EMAIL
from packages.benchmarks.graphrag_benchmark import run_graphrag_benchmark_item
from packages.benchmarks.memory_benchmark import run_memory_benchmark_item
from packages.benchmarks.metrics import aggregate_metrics
from packages.benchmarks.permission_benchmark import run_permission_benchmark_item
from packages.benchmarks.rag_benchmark import run_rag_benchmark_item
from packages.benchmarks.report_generator import export_reports
from packages.observability.trace_context import get_trace_id, resolve_trace_id, set_trace_id
from packages.common.db.models.benchmark import BenchmarkRun
from packages.common.db.models.role import UserRole
from packages.common.db.models.user import User


@dataclass
class BenchmarkConfig:
    name: str = "benchmark_run"
    mode: str = "secure_rag"
    limit: int | None = None
    dry_run: bool = False
    top_k: int = 5
    chunk_size: int = 512
    permission_filter: bool = True
    memory: bool = False
    question_types: list[str] = field(default_factory=list)
    dataset_path: Path | None = None
    export_reports: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BenchmarkConfig:
        config = data.get("config") or {}
        return cls(
            name=data.get("name", "benchmark_run"),
            mode=data.get("mode", "secure_rag"),
            limit=data.get("limit"),
            dry_run=bool(data.get("dry_run", False)),
            top_k=int(config.get("top_k", 5)),
            chunk_size=int(config.get("chunk_size", 512)),
            permission_filter=bool(config.get("permission_filter", True)),
            memory=bool(config.get("memory", False)),
            question_types=list(data.get("question_types") or []),
            dataset_path=Path(data["dataset_path"]) if data.get("dataset_path") else None,
            export_reports=bool(data.get("export_reports", True)),
        )


async def load_user_context_for_question(session: AsyncSession, question: EvalQuestion) -> UserContext:
    email = question.user_email or ROLE_EMAIL.get(question.user_role)
    if not email:
        raise ValueError(f"Unknown role: {question.user_role}")
    stmt = (
        select(User)
        .where(User.email == email, User.is_active.is_(True))
        .options(selectinload(User.user_roles).selectinload(UserRole.role))
    )
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is None:
        raise ValueError(f"User not found for email={email}")
    roles = [link.role.name for link in user.user_roles if link.role is not None]
    return build_user_context(
        user_id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        department=user.department,
        roles=roles,
        supplier_id=user.supplier_id,
    )


async def load_admin_context(session: AsyncSession) -> UserContext:
    return await load_user_context_for_question(
        session,
        EvalQuestion(id="admin", question="", user_role="admin", expected_mode="secure_rag", question_type="general"),
    )


async def run_single_question(
    session: AsyncSession,
    question: EvalQuestion,
    config: BenchmarkConfig,
) -> dict[str, Any]:
    user_context = await load_user_context_for_question(session, question)
    mode = config.mode

    if mode in {"secure_rag", "naive_rag", "hybrid_rag", "secure_rag_memory", "hybrid_rag_memory"}:
        if mode == "naive_rag":
            permission_filter = False
        elif mode in {"secure_rag_memory", "hybrid_rag_memory"}:
            permission_filter = config.permission_filter
            if config.memory:
                return await run_memory_benchmark_item(session, user_context, question)
        else:
            permission_filter = config.permission_filter
        return await run_rag_benchmark_item(
            session,
            user_context,
            question,
            mode=mode,
            top_k=config.top_k,
            chunk_size=config.chunk_size,
            permission_filter=permission_filter,
        )
    if mode == "graphrag":
        return await run_graphrag_benchmark_item(session, user_context, question, top_k=config.top_k)
    if mode == "memory":
        return await run_memory_benchmark_item(session, user_context, question)
    if mode == "permission":
        return await run_permission_benchmark_item(
            session,
            user_context,
            question,
            top_k=config.top_k,
            chunk_size=config.chunk_size,
        )
    raise ValueError(f"Unsupported benchmark mode: {mode}")


def _modes_for_all() -> list[str]:
    return ["secure_rag", "graphrag", "memory", "permission"]


async def run_benchmark(
    session: AsyncSession,
    *,
    admin_context: UserContext,
    config: BenchmarkConfig,
    target_run: BenchmarkRun | None = None,
) -> dict[str, Any]:
    dataset = load_dataset(config.dataset_path or default_dataset_path())
    questions = filter_questions(dataset, mode=None if config.mode == "all" else config.mode, question_types=config.question_types or None)
    if config.limit is not None:
        questions = questions[: config.limit]

    if config.dry_run:
        return {
            "status": "dry_run",
            "question_count": len(questions),
            "mode": config.mode,
            "config": config.__dict__,
        }

    modes = _modes_for_all() if config.mode == "all" else [config.mode]
    all_rows: list[dict[str, Any]] = []
    run_ids: list[str] = []
    primary_trace_id = resolve_trace_id()
    set_trace_id(primary_trace_id)
    container_run = target_run

    for mode in modes:
        mode_questions = filter_questions(dataset, mode=mode, question_types=config.question_types or None)
        if config.limit is not None:
            mode_questions = mode_questions[: config.limit]
        if not mode_questions:
            continue

        mode_config = BenchmarkConfig(
            name=f"{config.name}_{mode}" if config.mode == "all" else config.name,
            mode=mode,
            limit=config.limit,
            dry_run=False,
            top_k=config.top_k,
            chunk_size=config.chunk_size,
            permission_filter=config.permission_filter,
            memory=config.memory,
            question_types=config.question_types,
            dataset_path=config.dataset_path,
            export_reports=config.export_reports,
        )
        if target_run is not None and len(modes) == 1:
            run = target_run
        else:
            run = await create_benchmark_run(
                session,
                tenant_id=admin_context.tenant_id,
                user_id=admin_context.user_id,
                name=mode_config.name,
                mode=mode,
                config={
                    "top_k": mode_config.top_k,
                    "chunk_size": mode_config.chunk_size,
                    "permission_filter": mode_config.permission_filter,
                    "memory": mode_config.memory,
                    "unsafe_baseline": not mode_config.permission_filter or mode == "naive_rag",
                },
                trace_id=primary_trace_id,
            )
        run_ids.append(str(run.id))
        mode_rows: list[dict[str, Any]] = []

        for question in mode_questions:
            outcome = await run_single_question(session, question, mode_config)
            metrics = dict(outcome.get("metrics") or {})
            metrics["latency_ms"] = outcome.get("latency_ms", 0)
            metrics["question_type"] = question.question_type
            metrics["question_id"] = question.id
            token_usage = outcome.get("token_usage") or {}
            metrics["token_usage_total"] = int(token_usage.get("total_tokens", 0) or 0)

            await add_benchmark_result(
                session,
                benchmark_run_id=run.id,
                question_id=question.id,
                question=question.question,
                question_type=question.question_type,
                ground_truth=question.to_dict(),
                predicted_answer=outcome.get("predicted_answer"),
                metrics=metrics,
                latency_ms=int(outcome.get("latency_ms", 0)),
                token_usage=token_usage,
                retrieved_ids=outcome.get("retrieved_ids") or [],
                citations=outcome.get("citations") or [],
                graph_paths=outcome.get("graph_paths") or [],
                memory_used=outcome.get("memory_used") or [],
                error=outcome.get("error"),
                trace_id=primary_trace_id,
            )
            row = {"question_id": question.id, "question_type": question.question_type, **metrics}
            mode_rows.append(row)
            all_rows.append(row)

        summary = aggregate_metrics(mode_rows)
        summary["by_question_type"] = _group_metrics(mode_rows, "question_type")
        if not mode_config.permission_filter or mode == "naive_rag":
            summary["unsafe_baseline"] = True

        await finalize_benchmark_run(session, run, status="completed", summary=summary)
        if mode_config.export_reports and (target_run is None or run.id != target_run.id or len(modes) == 1):
            results = await list_benchmark_results(session, run.id)
            export_reports(run, results, summary)

    combined_summary = aggregate_metrics(all_rows) if all_rows else {}
    combined_summary["run_ids"] = run_ids
    combined_summary["trace_id"] = primary_trace_id

    if config.mode == "all" and container_run is not None:
        await finalize_benchmark_run(session, container_run, status="completed", summary=combined_summary)
        primary_run_id = container_run.id
    elif target_run is not None and target_run.status == "running" and not all_rows:
        await finalize_benchmark_run(
            session,
            target_run,
            status="failed",
            summary={},
            error_message="No benchmark questions matched the selected mode or limit.",
        )
        primary_run_id = target_run.id
    else:
        primary_run_id = run_ids[-1] if run_ids else (container_run.id if container_run else None)

    return {
        "benchmark_run_id": str(primary_run_id) if primary_run_id else None,
        "run_ids": run_ids,
        "trace_id": primary_trace_id,
        "status": "completed",
        "summary": combined_summary,
        "question_count": len(all_rows),
    }


def _group_metrics(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(str(row.get(key, "unknown")), []).append(row)
    return {name: aggregate_metrics(group_rows) for name, group_rows in groups.items()}


async def get_run_detail(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any] | None:
    run = await get_benchmark_run(session, run_id)
    if run is None:
        return None
    results = await list_benchmark_results(session, run_id)
    return {
        "run": run,
        "results": results,
        "summary": run.summary,
    }
