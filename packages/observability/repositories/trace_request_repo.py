"""Update trace request records."""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.trace_request import TraceRequest


async def write_trace_request(
    session: AsyncSession,
    *,
    request_id: str,
    trace_id: str,
    method: str,
    path: str,
    tenant_id: Any = None,
    user_id: Any = None,
    status_code: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> TraceRequest:
    row = TraceRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        request_id=request_id,
        trace_id=trace_id,
        method=method,
        path=path,
        status_code=status_code,
        metadata_=metadata or {},
    )
    session.add(row)
    await session.flush()
    return row


async def update_trace_request_status(
    session: AsyncSession,
    *,
    trace_id: str,
    status_code: int,
) -> None:
    await session.execute(
        update(TraceRequest)
        .where(TraceRequest.trace_id == trace_id)
        .values(status_code=status_code)
    )
    await session.flush()
