"""Finalize trace request status after HTTP response."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from packages.common.db.session import get_session_factory
from packages.observability.tracing import finalize_http_trace


class TraceFinalizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        trace_id = getattr(request.state, "trace_id", None)
        if trace_id:
            session_factory = get_session_factory()
            async with session_factory() as session:
                await finalize_http_trace(session, trace_id=trace_id, status_code=response.status_code)
                await session.commit()
        return response
