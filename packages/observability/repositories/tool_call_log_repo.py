"""Tool call log repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.common.db.models.tool_call_log import ToolCallLog


async def write_tool_call_log(
    session: AsyncSession,
    *,
    user_context: UserContext,
    tool_name: str,
    tool_input: dict[str, Any],
    tool_output: dict[str, Any],
    trace_id: str,
    agent_run_id: uuid.UUID | str | None = None,
    permission_decision: str,
    approval_required: bool,
    status: str,
    latency_ms: int,
    error_message: str | None = None,
    tool_call_id: str | None = None,
) -> ToolCallLog:
    run_uuid: uuid.UUID | None = None
    if agent_run_id:
        run_uuid = agent_run_id if isinstance(agent_run_id, uuid.UUID) else uuid.UUID(str(agent_run_id))

    row = ToolCallLog(
        id=uuid.UUID(tool_call_id) if tool_call_id else uuid.uuid4(),
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        agent_run_id=run_uuid,
        tool_name=tool_name,
        tool_input=tool_input,
        tool_output=tool_output,
        permission_decision=permission_decision,
        approval_required=approval_required,
        status=status,
        latency_ms=latency_ms,
        error_message=error_message,
    )
    session.add(row)
    await session.flush()
    return row
