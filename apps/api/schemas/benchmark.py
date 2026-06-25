"""Benchmark API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BenchmarkConfigInput(BaseModel):
    top_k: int = Field(default=5, ge=1, le=50)
    chunk_size: int = Field(default=512, ge=128, le=2048)
    permission_filter: bool = True
    memory: bool = False


class BenchmarkRunRequest(BaseModel):
    name: str
    mode: str = "secure_rag"
    limit: int | None = Field(default=20, ge=1, le=500)
    dry_run: bool = False
    config: BenchmarkConfigInput = Field(default_factory=BenchmarkConfigInput)


class BenchmarkSummary(BaseModel):
    recall_at_k: float | None = None
    precision_at_k: float | None = None
    citation_accuracy: float | None = None
    permission_violation_rate: float | None = None
    graph_path_hit_rate: float | None = None
    memory_hit_rate: float | None = None
    p95_latency_ms: float | None = None
    failure_rate: float | None = None
    count: int | None = None


class BenchmarkRunResponse(BaseModel):
    benchmark_run_id: UUID | None
    trace_id: str | None = None
    status: str
    summary: dict[str, Any]


class BenchmarkRunListItem(BaseModel):
    id: UUID
    name: str
    mode: str
    status: str
    summary: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None


class BenchmarkResultItem(BaseModel):
    id: UUID
    question_id: str
    question_type: str
    question: str
    metrics: dict[str, Any]
    latency_ms: int
    error: str | None = None


class BenchmarkReportResponse(BaseModel):
    benchmark_run_id: UUID
    markdown_path: str | None = None
    json_path: str | None = None
    csv_path: str | None = None
    summary: dict[str, Any]
