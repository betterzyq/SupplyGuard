"""Secure RAG query routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.schemas.rag import CitationItem, RAGQueryRequest, RAGQueryResponse, RAGRetrievalMeta
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.observability.tracing import begin_http_trace
from packages.observability.trace_context import set_trace_id
from packages.rag.secure_rag import run_secure_rag_query

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    payload: RAGQueryRequest,
    request: Request,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> RAGQueryResponse:
    trace_id = await begin_http_trace(
        session,
        user_context=user_context,
        method=request.method,
        path=str(request.url.path),
        trace_id_header=request.headers.get("X-Trace-Id"),
    )
    set_trace_id(trace_id)
    request.state.trace_id = trace_id

    result = await run_secure_rag_query(
        session,
        user_context,
        payload.query,
        trace_id=trace_id,
        top_k=payload.top_k,
        chunk_size_config=payload.chunk_size,
        doc_type=payload.doc_type,
        supplier_id=payload.supplier_id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()

    return RAGQueryResponse(
        query=result.query,
        answer=result.answer,
        citations=[CitationItem(**item.to_dict()) for item in result.citations],
        trace_id=result.trace_id,
        status=result.status,
        retrieval=RAGRetrievalMeta(
            top_k=result.retrieval["top_k"],
            result_count=result.retrieval["result_count"],
            filter_applied=result.retrieval["filter_applied"],
            latency_ms=result.retrieval.get("latency_ms"),
        ),
    )
