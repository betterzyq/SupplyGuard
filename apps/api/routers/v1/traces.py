"""Trace inspection routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.schemas.trace import TraceDetailResponse, TraceSummary, TraceTimelineItem
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.observability.trace_reader import load_trace

router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("/{trace_id}", response_model=TraceDetailResponse)
async def get_trace(
    trace_id: str,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> TraceDetailResponse:
    payload = await load_trace(session, trace_id, user_context)
    summary = payload.get("summary") or {}
    return TraceDetailResponse(
        trace_id=payload["trace_id"],
        request=payload.get("request") or {},
        agent_run=payload.get("agent_run"),
        retrieval_logs=payload.get("retrieval_logs") or [],
        graph_retrieval_logs=payload.get("graph_retrieval_logs") or [],
        audit_logs=payload.get("audit_logs") or [],
        memory_events=payload.get("memory_events") or [],
        tool_calls=payload.get("tool_calls") or [],
        benchmark_results=payload.get("benchmark_results") or [],
        benchmark_runs=payload.get("benchmark_runs") or [],
        node_spans=payload.get("node_spans") or [],
        timeline=[TraceTimelineItem(**item) for item in payload.get("timeline") or []],
        summary=TraceSummary(**summary),
    )
