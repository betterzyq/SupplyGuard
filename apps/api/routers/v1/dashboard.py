"""Dashboard aggregation routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.routers.v1.health import health_dependencies
from packages.authz.rbac import UserContext
from packages.benchmarks.benchmark_repo import list_benchmark_runs
from packages.common.db.models.audit_log import AuditLog
from packages.common.db.session import get_db_session
from packages.common.config import get_settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def dashboard_summary(
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    settings = get_settings()
    health = await health_dependencies()

    benchmark_snapshot = None
    if user_context.is_admin:
        runs = await list_benchmark_runs(session, user_context.tenant_id, limit=1)
        if runs:
            benchmark_snapshot = runs[0].summary or {}

    denied_count = (
        await session.execute(
            select(func.count())
            .select_from(AuditLog)
            .where(
                AuditLog.tenant_id == user_context.tenant_id,
                AuditLog.permission_decision == "denied",
            )
        )
    ).scalar_one()

    total_audit = (
        await session.execute(
            select(func.count()).select_from(AuditLog).where(AuditLog.tenant_id == user_context.tenant_id)
        )
    ).scalar_one()

    llm_dep = health.get("dependencies", {}).get("llm", {})
    embedding_dep = health.get("dependencies", {}).get("embedding", {})
    deps = health.get("dependencies", {})

    runs_for_status = await list_benchmark_runs(session, user_context.tenant_id, limit=1)
    eval_path = Path(__file__).resolve().parents[3] / "data" / "eval" / "supplyguard_eval.jsonl"
    if embedding_dep.get("status") != "ok":
        benchmark_status = "error"
    elif runs_for_status:
        benchmark_status = "ok"
    elif eval_path.exists():
        benchmark_status = "no_data"
    else:
        benchmark_status = "no_data"

    capability_status = {
        "secure_rag": deps.get("qdrant", {}).get("status", "unknown"),
        "graphrag": deps.get("neo4j", {}).get("status", "unknown"),
        "memory": deps.get("redis", {}).get("status", "unknown"),
        "llm": llm_dep.get("status", "unknown"),
        "embedding": embedding_dep.get("status", "unknown"),
        "benchmark": benchmark_status,
        "observability": deps.get("postgres", {}).get("status", "unknown"),
    }

    return {
        "health": health,
        "benchmark_snapshot": benchmark_snapshot,
        "audit_stats": {"total": total_audit, "denied_count": denied_count},
        "capability_status": capability_status,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_model": llm_dep.get("model"),
        "environment": settings.APP_ENV,
    }
