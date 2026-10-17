"""Authenticated local report exports, backed by the P5 tenant workspace."""

import uuid
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from packages.authz.rbac import UserContext
from packages.operations.schemas import ReportRequest
from packages.operations.service import idempotent
from packages.operations.reports import create_report


async def export_risk_report(
    session: AsyncSession, user_context: UserContext, tool_input: dict[str, Any]
) -> dict[str, Any]:
    request = ReportRequest(kind="risk", format="xlsx")
    return await idempotent(
        session,
        user_context,
        "tool.risk.export",
        str(tool_input.get("idempotency_key") or uuid.uuid4()),
        request.model_dump(mode="json"),
        lambda: create_report(session, user_context, request),
    )


async def export_benchmark_results(
    session: AsyncSession, user_context: UserContext, tool_input: dict[str, Any]
) -> dict[str, Any]:
    request = ReportRequest(
        kind="evaluation",
        format="xlsx",
        benchmark_run_id=tool_input.get("benchmark_run_id") or None,
    )
    return await idempotent(
        session,
        user_context,
        "tool.evaluation.export",
        str(tool_input.get("idempotency_key") or uuid.uuid4()),
        request.model_dump(mode="json"),
        lambda: create_report(session, user_context, request),
    )
