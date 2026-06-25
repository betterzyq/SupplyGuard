"""Request/trace context propagation via contextvars."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Any

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def get_request_id() -> str | None:
    return request_id_var.get()


def get_trace_id() -> str | None:
    return trace_id_var.get()


def set_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def set_trace_id(trace_id: str) -> None:
    trace_id_var.set(trace_id)


def set_user_context_ids(*, user_id: str | None = None, tenant_id: str | None = None) -> None:
    if user_id is not None:
        user_id_var.set(user_id)
    if tenant_id is not None:
        tenant_id_var.set(tenant_id)


def resolve_trace_id(*, header_value: str | None = None) -> str:
    if header_value:
        return header_value.strip()
    existing = get_trace_id()
    if existing:
        return existing
    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    return trace_id


def get_context_snapshot() -> dict[str, Any]:
    return {
        "request_id": get_request_id(),
        "trace_id": get_trace_id(),
        "user_id": user_id_var.get(),
        "tenant_id": tenant_id_var.get(),
    }
