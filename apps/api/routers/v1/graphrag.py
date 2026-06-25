"""GraphRAG HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from apps.api.schemas.graphrag import GraphPathItem, GraphRAGQueryRequest, GraphRAGQueryResponse
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.graphrag.graph_retriever import execute_graph_query
from packages.observability.tracing import begin_http_trace
from packages.observability.trace_context import set_trace_id

router = APIRouter(prefix="/graphrag", tags=["graphrag"])


@router.post("/query", response_model=GraphRAGQueryResponse)
async def graphrag_query(
    payload: GraphRAGQueryRequest,
    request: Request,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> GraphRAGQueryResponse:
    trace_id = await begin_http_trace(
        session,
        user_context=user_context,
        method=request.method,
        path=str(request.url.path),
        trace_id_header=request.headers.get("X-Trace-Id"),
    )
    set_trace_id(trace_id)
    request.state.trace_id = trace_id

    result = await execute_graph_query(
        user_context,
        query=payload.query,
        query_type=payload.query_type,
        entity_code=payload.entity_code,
        top_k=payload.top_k,
        trace_id=trace_id,
        session=session,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()

    if result.permission_decision == "denied":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=result.error_message or "Graph query denied",
        )

    graph_paths = [
        GraphPathItem(
            path_index=path.path_index,
            path_text=path.path_text,
            nodes=[node.to_dict() for node in path.nodes],
            relationships=[rel.to_dict() for rel in path.relationships],
            template_id=path.template_id,
            graph_path_ref=f"{path.template_id}#path_{path.path_index}",
        )
        for path in result.graph_paths
    ]

    return GraphRAGQueryResponse(
        query=result.query,
        query_type=result.query_type,
        matched_entities=result.matched_entities,
        graph_paths=graph_paths,
        affected_suppliers=result.affected_suppliers,
        affected_materials=result.affected_materials,
        affected_products=result.affected_products,
        affected_orders=result.affected_orders,
        affected_customers=result.affected_customers,
        cypher_template=result.cypher_template,
        trace_id=result.trace_id,
        latency_ms=result.latency_ms,
        result_count=result.result_count,
        permission_decision=result.permission_decision,
        error_message=result.error_message,
    )
