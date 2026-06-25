"""Trace lifecycle helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.observability.repositories.trace_request_repo import (
    update_trace_request_status,
    write_trace_request,
)
from packages.observability.trace_context import get_request_id, resolve_trace_id, set_trace_id


async def begin_http_trace(
    session: AsyncSession | None,
    *,
    user_context: UserContext | None,
    method: str,
    path: str,
    trace_id_header: str | None = None,
    trace_id: str | None = None,
) -> str:
    resolved = trace_id or resolve_trace_id(header_value=trace_id_header)
    set_trace_id(resolved)
    if session is not None:
        await write_trace_request(
            session,
            request_id=get_request_id() or resolved,
            trace_id=resolved,
            method=method,
            path=path,
            tenant_id=user_context.tenant_id if user_context else None,
            user_id=user_context.user_id if user_context else None,
        )
    return resolved


async def finalize_http_trace(
    session: AsyncSession | None,
    *,
    trace_id: str | None,
    status_code: int,
) -> None:
    if session is None or not trace_id:
        return
    await update_trace_request_status(session, trace_id=trace_id, status_code=status_code)


def attach_trace_metadata(payload: dict[str, Any], trace_id: str) -> dict[str, Any]:
    payload["trace_id"] = trace_id
    payload["request_id"] = get_request_id()
    return payload
