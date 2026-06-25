"""Tool API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolDefinitionItem(BaseModel):
    name: str
    description: str
    server: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    high_risk: bool = False


class ToolListResponse(BaseModel):
    tools: list[ToolDefinitionItem]


class ToolCallRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    tool_input: dict[str, Any] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    tool_name: str
    status: str
    result: dict[str, Any] = Field(default_factory=dict)
    trace_id: str
    tool_call_id: str | None = None
    permission_decision: str = "allowed"
    approval_required: bool = False
    latency_ms: int = 0
    error_message: str | None = None
