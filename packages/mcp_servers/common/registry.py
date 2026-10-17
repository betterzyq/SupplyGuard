"""Tool registry and unified execution."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.authz.tool_policy import check_tool_permission
from packages.mcp_servers.common.errors import ToolNotFoundError
from packages.mcp_servers.common.permissions import list_allowed_tools
from packages.mcp_servers.common.schemas import ToolDefinition, ToolExecutionResult
from packages.mcp_servers.excel_report_mcp import tools as excel_tools
from packages.mcp_servers.logistics_mcp import tools as logistics_tools
from packages.mcp_servers.supplier_db_mcp import tools as supplier_tools
from packages.observability.repositories.tool_call_log_repo import write_tool_call_log

ToolHandler = Callable[
    [AsyncSession, UserContext, dict[str, Any]], Awaitable[dict[str, Any]]
]

TOOL_DEFINITIONS: dict[str, ToolDefinition] = {
    "query_supplier_profile": ToolDefinition(
        name="query_supplier_profile",
        description="Query supplier profile by supplier_code or supplier_id",
        server="supplier_db_mcp",
        input_schema={"supplier_code": "string", "supplier_id": "string"},
    ),
    "query_supplier_risk_events": ToolDefinition(
        name="query_supplier_risk_events",
        description="List recent risk events for a supplier",
        server="supplier_db_mcp",
        input_schema={"supplier_code": "string", "limit": "integer"},
    ),
    "query_supplier_delivery_history": ToolDefinition(
        name="query_supplier_delivery_history",
        description="List recent delivery orders for a supplier",
        server="supplier_db_mcp",
        input_schema={"supplier_code": "string", "limit": "integer"},
    ),
    "query_supplier_contract_summary": ToolDefinition(
        name="query_supplier_contract_summary",
        description="Summarize contract documents for a supplier",
        server="supplier_db_mcp",
        input_schema={"supplier_code": "string"},
    ),
    "query_delivery_status": ToolDefinition(
        name="query_delivery_status",
        description="Query delivery status by order_no or supplier_code",
        server="logistics_mcp",
        input_schema={"order_no": "string", "supplier_code": "string"},
    ),
    "query_delay_events": ToolDefinition(
        name="query_delay_events",
        description="List delivery delay events",
        server="logistics_mcp",
        input_schema={"supplier_code": "string"},
    ),
    "query_route_info": ToolDefinition(
        name="query_route_info",
        description="Query logistics route info",
        server="logistics_mcp",
        input_schema={"origin": "string", "destination": "string"},
    ),
    "export_risk_report": ToolDefinition(
        name="export_risk_report",
        description="Generate authenticated tenant risk report download",
        server="excel_report_mcp",
        input_schema={},
        high_risk=False,
    ),
    "export_benchmark_results": ToolDefinition(
        name="export_benchmark_results",
        description="Generate authenticated evaluation report download",
        server="excel_report_mcp",
        input_schema={"benchmark_run_id": "string"},
        high_risk=False,
    ),
}

TOOL_HANDLERS: dict[str, ToolHandler] = {
    "query_supplier_profile": supplier_tools.query_supplier_profile,
    "query_supplier_risk_events": supplier_tools.query_supplier_risk_events,
    "query_supplier_delivery_history": supplier_tools.query_supplier_delivery_history,
    "query_supplier_contract_summary": supplier_tools.query_supplier_contract_summary,
    "query_delivery_status": logistics_tools.query_delivery_status,
    "query_delay_events": logistics_tools.query_delay_events,
    "query_route_info": logistics_tools.query_route_info,
    "export_risk_report": excel_tools.export_risk_report,
    "export_benchmark_results": excel_tools.export_benchmark_results,
}


def get_tool_definitions_for_user(user_context: UserContext) -> list[ToolDefinition]:
    allowed = set(list_allowed_tools(user_context))
    return [
        TOOL_DEFINITIONS[name] for name in sorted(allowed) if name in TOOL_DEFINITIONS
    ]


async def execute_tool_call(
    session: AsyncSession,
    user_context: UserContext,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
    *,
    trace_id: str | None = None,
    agent_run_id: uuid.UUID | str | None = None,
) -> ToolExecutionResult:
    tool_input = dict(tool_input or {})
    trace_id = trace_id or str(uuid.uuid4())
    tool_call_id = str(uuid.uuid4())
    started = time.perf_counter()

    if tool_name not in TOOL_DEFINITIONS:
        result = ToolExecutionResult(
            tool_name=tool_name,
            status="failed",
            result={"error": f"unknown tool: {tool_name}"},
            tool_call_id=tool_call_id,
            trace_id=trace_id,
            permission_decision="denied",
            error_message=f"unknown tool: {tool_name}",
        )
        await write_tool_call_log(
            session,
            user_context=user_context,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result.result,
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            permission_decision="denied",
            approval_required=False,
            status="failed",
            latency_ms=0,
            error_message=result.error_message,
            tool_call_id=tool_call_id,
        )
        raise ToolNotFoundError(tool_name)

    permission = check_tool_permission(user_context, tool_name, tool_input)
    if not permission.allowed:
        latency_ms = int((time.perf_counter() - started) * 1000)
        result = ToolExecutionResult(
            tool_name=tool_name,
            status="denied",
            result={"error": permission.reason, "status": "denied"},
            tool_call_id=tool_call_id,
            trace_id=trace_id,
            permission_decision=permission.permission_decision,
            error_message=permission.reason,
            latency_ms=latency_ms,
        )
        await write_tool_call_log(
            session,
            user_context=user_context,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result.result,
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            permission_decision=permission.permission_decision,
            approval_required=False,
            status="denied",
            latency_ms=latency_ms,
            error_message=permission.reason,
            tool_call_id=tool_call_id,
        )
        return result

    if permission.approval_required:
        latency_ms = int((time.perf_counter() - started) * 1000)
        result = ToolExecutionResult(
            tool_name=tool_name,
            status="approval_required",
            result={
                "status": "approval_required",
                "message": permission.reason,
                "tool_name": tool_name,
            },
            tool_call_id=tool_call_id,
            trace_id=trace_id,
            permission_decision=permission.permission_decision,
            approval_required=True,
            latency_ms=latency_ms,
        )
        await write_tool_call_log(
            session,
            user_context=user_context,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=result.result,
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            permission_decision=permission.permission_decision,
            approval_required=True,
            status="approval_required",
            latency_ms=latency_ms,
            tool_call_id=tool_call_id,
        )
        return result

    handler = TOOL_HANDLERS[tool_name]
    try:
        output = await handler(session, user_context, tool_input)
        latency_ms = int((time.perf_counter() - started) * 1000)
        if output.get("status") == "denied" or output.get("error"):
            status = "denied"
        elif output.get("status") == "not_implemented":
            status = "not_implemented"
        else:
            status = "success"
        result = ToolExecutionResult(
            tool_name=tool_name,
            status=status,
            result=output,
            tool_call_id=tool_call_id,
            trace_id=trace_id,
            permission_decision="allowed",
            latency_ms=latency_ms,
            error_message=output.get("error") if status != "success" else None,
        )
        await write_tool_call_log(
            session,
            user_context=user_context,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=output,
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            permission_decision="allowed",
            approval_required=False,
            status=status,
            latency_ms=latency_ms,
            error_message=result.error_message,
            tool_call_id=tool_call_id,
        )
        return result
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        output = {"error": str(exc), "status": "failed"}
        result = ToolExecutionResult(
            tool_name=tool_name,
            status="failed",
            result=output,
            tool_call_id=tool_call_id,
            trace_id=trace_id,
            permission_decision="allowed",
            latency_ms=latency_ms,
            error_message=str(exc),
        )
        await write_tool_call_log(
            session,
            user_context=user_context,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=output,
            trace_id=trace_id,
            agent_run_id=agent_run_id,
            permission_decision="allowed",
            approval_required=False,
            status="failed",
            latency_ms=latency_ms,
            error_message=str(exc),
            tool_call_id=tool_call_id,
        )
        return result


def format_tool_evidence_content(tool_name: str, result: dict[str, Any]) -> str:
    return json.dumps(
        {"tool": tool_name, "result": result}, ensure_ascii=False, indent=2
    )
