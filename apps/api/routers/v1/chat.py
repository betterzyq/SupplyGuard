"""Chat workflow routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.schemas.chat import ChatRequest, ChatResponse, ContextBudget
from apps.api.schemas.rag import CitationItem
from packages.agents.graph import run_chat_workflow
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.observability.tracing import begin_http_trace
from packages.observability.trace_context import set_trace_id

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    trace_id = await begin_http_trace(
        session,
        user_context=user_context,
        method=request.method,
        path=str(request.url.path),
        trace_id_header=request.headers.get("X-Trace-Id"),
    )
    set_trace_id(trace_id)
    request.state.trace_id = trace_id

    result = await run_chat_workflow(
        session,
        user_context,
        payload.query,
        session_id=payload.session_id,
        top_k=payload.top_k,
        use_memory=payload.use_memory,
        ip_address=request.client.host if request.client else None,
        trace_id=trace_id,
    )
    budget = result.get("context_budget") or {}
    context_budget = None
    if budget:
        context_budget = ContextBudget(
            max_tokens=int(budget.get("max_tokens", 0)),
            used_tokens=int(budget.get("used_tokens", 0)),
        )
    return ChatResponse(
        answer=result["answer"],
        citations=[CitationItem(**item) for item in result["citations"]],
        memory_used=result.get("memory_used") or [],
        memory_written=result.get("memory_written") or [],
        context_budget=context_budget,
        trace_id=result["trace_id"],
        agent_run_id=result["agent_run_id"],
        nodes_executed=result["nodes_executed"],
        token_usage=result["token_usage"],
        status=result["status"],
        route_mode=result.get("route_mode"),
    )
