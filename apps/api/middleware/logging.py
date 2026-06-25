"""Structured logging context middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from packages.common.logging import get_logger
from packages.observability.trace_context import get_request_id, get_trace_id, set_user_context_ids

logger = get_logger("api.middleware.logging")


class LoggingContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        bound = logger.bind(
            request_id=get_request_id(),
            trace_id=get_trace_id(),
            path=request.url.path,
            method=request.method,
        )
        if hasattr(request.state, "user_id"):
            set_user_context_ids(user_id=str(request.state.user_id))
        try:
            response = await call_next(request)
            bound.info(
                "http_request_completed status={}",
                response.status_code,
            )
            return response
        except Exception:
            bound.exception("http_request_failed")
            raise
