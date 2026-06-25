"""MCP tool schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    server: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    high_risk: bool = False


@dataclass
class ToolExecutionResult:
    tool_name: str
    status: str  # success | denied | approval_required | failed
    result: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None
    trace_id: str | None = None
    permission_decision: str = "allowed"
    approval_required: bool = False
    latency_ms: int = 0
    error_message: str | None = None
