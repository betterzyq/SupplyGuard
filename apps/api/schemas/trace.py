"""Trace API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TraceSummary(BaseModel):
    total_latency_ms: int = 0
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost: float = 0.0
    model: str | None = None
    retrieval_count: int = 0
    permission_denied_count: int = 0
    error_count: int = 0
    node_count: int = 0


class TraceTimelineItem(BaseModel):
    type: str
    name: str
    latency_ms: int | None = None
    status: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    error_message: str | None = None


class TraceDetailResponse(BaseModel):
    trace_id: str
    request: dict[str, Any] = Field(default_factory=dict)
    agent_run: dict[str, Any] | None = None
    retrieval_logs: list[dict[str, Any]] = Field(default_factory=list)
    graph_retrieval_logs: list[dict[str, Any]] = Field(default_factory=list)
    audit_logs: list[dict[str, Any]] = Field(default_factory=list)
    memory_events: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_results: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_runs: list[dict[str, Any]] = Field(default_factory=list)
    node_spans: list[dict[str, Any]] = Field(default_factory=list)
    timeline: list[TraceTimelineItem] = Field(default_factory=list)
    summary: TraceSummary
