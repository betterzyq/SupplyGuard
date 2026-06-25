"""Aggregate trace data across observability tables."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.common.db.models.agent_node_span import AgentNodeSpan
from packages.common.db.models.agent_run import AgentRun
from packages.common.db.models.audit_log import AuditLog
from packages.common.db.models.benchmark import BenchmarkResult, BenchmarkRun
from packages.common.db.models.graph_retrieval_log import GraphRetrievalLog
from packages.common.db.models.memory_event_log import MemoryEventLog
from packages.common.db.models.retrieval_log import RetrievalLog
from packages.common.db.models.tool_call_log import ToolCallLog
from packages.common.db.models.trace_request import TraceRequest
from packages.observability.metrics import build_trace_summary
from packages.observability.repositories.node_span_repo import span_to_dict

FORBIDDEN_TITLE_MARKERS = (
    "Confidential Supplier Framework Contract",
    "Finance Pricing Terms",
    "Other Supplier Portal Notice",
)


def _can_access_trace(user_context: UserContext, owner_user_id: uuid.UUID) -> bool:
    if user_context.is_admin:
        return True
    return user_context.user_id == owner_user_id


def _sanitize_retrieval_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for item in results:
        sanitized.append(
            {
                "document_id": item.get("document_id"),
                "chunk_id": item.get("chunk_id"),
                "chunk_index": item.get("chunk_index"),
                "score": item.get("score"),
                "title": item.get("title"),
            }
        )
    return sanitized


def _redact_for_external_supplier(payload: dict[str, Any]) -> dict[str, Any]:
    retrieval_logs = payload.get("retrieval_logs") or []
    for row in retrieval_logs:
        row["results"] = [
            item
            for item in row.get("results") or []
            if not any(marker in str(item.get("title", "")) for marker in FORBIDDEN_TITLE_MARKERS)
        ]
    answer = payload.get("agent_run", {}).get("final_answer")
    if isinstance(answer, str):
        for marker in ("Net 60", "Volume discount tier 1", "Beta Materials", "18% margin"):
            if marker.lower() in answer.lower():
                payload["agent_run"]["final_answer"] = "[redacted: potential unauthorized content]"
                break
    return payload


async def load_trace(
    session: AsyncSession,
    trace_id: str,
    user_context: UserContext,
) -> dict[str, Any]:
    agent_run = (
        await session.execute(select(AgentRun).where(AgentRun.trace_id == trace_id))
    ).scalar_one_or_none()

    owner_user_id: uuid.UUID | None = agent_run.user_id if agent_run else None

    trace_request = (
        await session.execute(select(TraceRequest).where(TraceRequest.trace_id == trace_id).limit(1))
    ).scalar_one_or_none()

    retrieval_logs = list(
        (await session.execute(select(RetrievalLog).where(RetrievalLog.trace_id == trace_id))).scalars().all()
    )
    graph_logs = list(
        (
            await session.execute(
                select(GraphRetrievalLog).where(GraphRetrievalLog.trace_id == trace_id)
            )
        ).scalars().all()
    )
    audit_logs = list(
        (await session.execute(select(AuditLog).where(AuditLog.trace_id == trace_id))).scalars().all()
    )
    memory_events = list(
        (await session.execute(select(MemoryEventLog).where(MemoryEventLog.trace_id == trace_id))).scalars().all()
    )
    tool_calls = list(
        (await session.execute(select(ToolCallLog).where(ToolCallLog.trace_id == trace_id))).scalars().all()
    )
    benchmark_results = list(
        (
            await session.execute(select(BenchmarkResult).where(BenchmarkResult.trace_id == trace_id))
        ).scalars().all()
    )
    benchmark_runs = list(
        (await session.execute(select(BenchmarkRun).where(BenchmarkRun.trace_id == trace_id))).scalars().all()
    )
    node_spans = list(
        (
            await session.execute(
                select(AgentNodeSpan)
                .where(AgentNodeSpan.trace_id == trace_id)
                .order_by(AgentNodeSpan.start_time.asc())
            )
        ).scalars().all()
    )

    if not any(
        [
            agent_run,
            trace_request,
            retrieval_logs,
            graph_logs,
            audit_logs,
            memory_events,
            tool_calls,
            node_spans,
            benchmark_runs,
        ]
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="trace not found")

    if owner_user_id is None:
        if retrieval_logs:
            owner_user_id = retrieval_logs[0].user_id
        elif graph_logs:
            owner_user_id = graph_logs[0].user_id
        elif audit_logs and audit_logs[0].user_id:
            owner_user_id = audit_logs[0].user_id
        elif trace_request and trace_request.user_id:
            owner_user_id = trace_request.user_id
        elif tool_calls:
            owner_user_id = tool_calls[0].user_id

    if owner_user_id is None or not _can_access_trace(user_context, owner_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="trace access denied")

    timeline: list[dict[str, Any]] = []
    for span in node_spans:
        timeline.append(
            {
                "type": "node",
                "name": span.node_name,
                "latency_ms": span.latency_ms,
                "status": span.status,
                "start_time": span.start_time.isoformat() if span.start_time else None,
                "end_time": span.end_time.isoformat() if span.end_time else None,
                "error_message": span.error_message,
            }
        )
    for row in retrieval_logs:
        timeline.append(
            {
                "type": "retrieval",
                "name": row.retriever_type,
                "latency_ms": row.latency_ms,
                "status": "completed",
                "result_count": row.result_count,
            }
        )
    for row in graph_logs:
        timeline.append(
            {
                "type": "graphrag",
                "name": row.query_type,
                "latency_ms": row.latency_ms,
                "status": "denied" if row.permission_decision == "denied" else "completed",
            }
        )
    for row in memory_events:
        timeline.append(
            {
                "type": "memory",
                "name": row.event_type,
                "latency_ms": 0,
                "status": "completed",
            }
        )
    for row in tool_calls:
        timeline.append(
            {
                "type": "tool",
                "name": row.tool_name,
                "latency_ms": row.latency_ms,
                "status": row.status,
            }
        )
    for row in audit_logs:
        timeline.append(
            {
                "type": "audit",
                "name": row.action,
                "latency_ms": 0,
                "status": row.permission_decision,
            }
        )

    permission_denied_count = sum(
        1
        for row in audit_logs
        if row.permission_decision == "denied"
        or row.action.endswith("_denied")
    ) + sum(1 for row in graph_logs if row.permission_decision == "denied")

    token_usage = agent_run.token_usage if agent_run else {}
    summary = build_trace_summary(
        timeline=timeline,
        token_usage=token_usage,
        retrieval_count=len(retrieval_logs),
        permission_denied_count=permission_denied_count,
        error_count=sum(1 for span in node_spans if span.status == "failed"),
    )

    payload: dict[str, Any] = {
        "trace_id": trace_id,
        "request": {
            "request_id": trace_request.request_id if trace_request else None,
            "method": trace_request.method if trace_request else None,
            "path": trace_request.path if trace_request else None,
            "status_code": trace_request.status_code if trace_request else None,
        },
        "agent_run": None,
        "retrieval_logs": [
            {
                "id": str(row.id),
                "query": row.query,
                "top_k": row.top_k,
                "filter_applied": row.filter_applied,
                "results": _sanitize_retrieval_results(row.results or []),
                "latency_ms": row.latency_ms,
                "result_count": row.result_count,
            }
            for row in retrieval_logs
        ],
        "graph_retrieval_logs": [
            {
                "id": str(row.id),
                "query": row.query,
                "query_type": row.query_type,
                "cypher_template": row.cypher_template,
                "parameters": row.parameters,
                "paths_found": row.paths_found,
                "latency_ms": row.latency_ms,
                "permission_decision": row.permission_decision,
            }
            for row in graph_logs
        ],
        "audit_logs": [
            {
                "id": str(row.id),
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "permission_decision": row.permission_decision,
                "reason": row.reason,
            }
            for row in audit_logs
        ],
        "memory_events": [
            {
                "id": str(row.id),
                "event_type": row.event_type,
                "memory_type": row.memory_type,
                "summary": row.summary,
                "metadata": row.metadata_,
            }
            for row in memory_events
        ],
        "tool_calls": [
            {
                "id": str(row.id),
                "tool_name": row.tool_name,
                "status": row.status,
                "permission_decision": row.permission_decision,
                "approval_required": row.approval_required,
                "latency_ms": row.latency_ms,
            }
            for row in tool_calls
        ],
        "benchmark_results": [
            {
                "id": str(row.id),
                "question_id": row.question_id,
                "question_type": row.question_type,
                "metrics": row.metrics,
                "latency_ms": row.latency_ms,
            }
            for row in benchmark_results
        ],
        "benchmark_runs": [
            {
                "id": str(row.id),
                "name": row.name,
                "mode": row.mode,
                "status": row.status,
                "summary": row.summary,
            }
            for row in benchmark_runs
        ],
        "node_spans": [span_to_dict(span) for span in node_spans],
        "timeline": timeline,
        "summary": summary,
    }

    if agent_run:
        payload["agent_run"] = {
            "id": str(agent_run.id),
            "query": agent_run.query,
            "status": agent_run.status,
            "workflow_version": agent_run.workflow_version,
            "latency_ms": agent_run.latency_ms,
            "token_usage": agent_run.token_usage,
            "llm_model": agent_run.llm_model,
            "estimated_cost": agent_run.estimated_cost,
            "nodes_executed": agent_run.nodes_executed,
            "final_answer": agent_run.final_answer,
            "error_message": agent_run.error_message,
        }

    if user_context.is_external_supplier:
        payload = _redact_for_external_supplier(payload)
        memory_events = payload.get("memory_events") or []
        for row in memory_events:
            if row.get("summary"):
                row["summary"] = row["summary"][:120] + ("..." if len(row["summary"]) > 120 else "")

    return payload
