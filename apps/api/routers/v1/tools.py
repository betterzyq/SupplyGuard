"""MCP tool routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.schemas.tool import (
    ToolCallRequest,
    ToolCallResponse,
    ToolDefinitionItem,
    ToolListResponse,
)
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.mcp_servers.common.registry import execute_tool_call, get_tool_definitions_for_user
from packages.observability.tracing import begin_http_trace
from packages.observability.trace_context import set_trace_id

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=ToolListResponse)
async def list_tools(
    user_context: UserContext = Depends(get_user_context),
) -> ToolListResponse:
    definitions = get_tool_definitions_for_user(user_context)
    return ToolListResponse(
        tools=[
            ToolDefinitionItem(
                name=item.name,
                description=item.description,
                server=item.server,
                input_schema=item.input_schema,
                high_risk=item.high_risk,
            )
            for item in definitions
        ]
    )


@router.post("/call", response_model=ToolCallResponse)
async def call_tool(
    payload: ToolCallRequest,
    request: Request,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ToolCallResponse:
    trace_id = await begin_http_trace(
        session,
        user_context=user_context,
        method=request.method,
        path=str(request.url.path),
        trace_id_header=request.headers.get("X-Trace-Id"),
    )
    set_trace_id(trace_id)
    request.state.trace_id = trace_id

    result = await execute_tool_call(
        session,
        user_context,
        payload.tool_name,
        payload.tool_input,
        trace_id=trace_id,
    )
    await session.commit()

    return ToolCallResponse(
        tool_name=result.tool_name,
        status=result.status,
        result=result.result,
        trace_id=result.trace_id or trace_id,
        tool_call_id=result.tool_call_id,
        permission_decision=result.permission_decision,
        approval_required=result.approval_required,
        latency_ms=result.latency_ms,
        error_message=result.error_message,
    )
