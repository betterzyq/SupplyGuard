"""Excel report MCP stub tools (approval required)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.common.db.models.benchmark import BenchmarkRun
from packages.common.db.models.risk_event import RiskEvent


async def export_risk_report(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    count = (
        await session.execute(
            select(func.count()).select_from(RiskEvent).where(RiskEvent.tenant_id == user_context.tenant_id)
        )
    ).scalar_one()
    return {
        "report_type": "risk_report",
        "format": "xlsx",
        "row_count": count,
        "download_url": None,
        "message": "Report generation requires approval (stub).",
    }


async def export_benchmark_results(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    run_id = tool_input.get("benchmark_run_id")
    count = (
        await session.execute(
            select(func.count()).select_from(BenchmarkRun).where(BenchmarkRun.tenant_id == user_context.tenant_id)
        )
    ).scalar_one()
    return {
        "report_type": "benchmark_export",
        "format": "xlsx",
        "benchmark_run_id": run_id,
        "available_runs": count,
        "download_url": None,
        "message": "Benchmark export requires approval (stub).",
    }
