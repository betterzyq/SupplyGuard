"""Supply chain impact simulation (GraphRAG aggregation)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_user_context
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.graphrag.graph_retriever import execute_graph_query
from packages.observability.tracing import begin_http_trace
from packages.observability.trace_context import set_trace_id

router = APIRouter(prefix="/supply-chain", tags=["supply-chain"])


class ImpactSimulationRequest(BaseModel):
    source_node_type: str = Field(default="supplier")
    source_node_code: str
    risk_type: str = Field(default="delivery_delay")
    severity: str = Field(default="high")
    max_hops: int = Field(default=5, ge=1, le=10)
    include_alternatives: bool = True
    include_documents: bool = False
    include_actions: bool = True


@router.post("/impact")
async def run_impact_simulation(
    payload: ImpactSimulationRequest,
    request: Request,
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    code = payload.source_node_code.upper()
    if code.startswith("S") and not code.startswith("SUP-"):
        digits = code.lstrip("S")
        if digits.isdigit():
            code = f"SUP-{digits.zfill(3)}"

    trace_id = await begin_http_trace(
        session,
        user_context=user_context,
        method=request.method,
        path=str(request.url.path),
        trace_id_header=request.headers.get("X-Trace-Id"),
    )
    set_trace_id(trace_id)

    query_type = "supplier_impact"
    if payload.source_node_type == "product":
        query_type = "product_dependency"
    elif payload.source_node_type == "customer":
        query_type = "customer_order_dependency"

    query_text = (
        f"Simulate {payload.severity} {payload.risk_type} at {payload.source_node_type} "
        f"{code}: what downstream materials, products, orders and customers are affected?"
    )

    result = await execute_graph_query(
        user_context,
        query=query_text,
        query_type=query_type,
        entity_code=code,
        top_k=20,
        trace_id=trace_id,
        session=session,
        ip_address=request.client.host if request.client else None,
    )

    alternatives: list[str] = []
    alt_paths: list[dict] = []
    if payload.include_alternatives and payload.source_node_type == "supplier":
        alt_result = await execute_graph_query(
            user_context,
            query=f"Alternative suppliers for {code}",
            query_type="supplier_alternatives",
            entity_code=code,
            top_k=10,
            trace_id=trace_id,
            session=session,
            ip_address=request.client.host if request.client else None,
        )
        alternatives = alt_result.affected_suppliers or []
        alt_paths = [p.to_dict() if hasattr(p, "to_dict") else p for p in alt_result.graph_paths]

    agent_actions = []
    if payload.include_actions:
        agent_actions = [
            {
                "action": "Notify procurement manager",
                "agent": "risk_agent",
                "permission": "procurement_manager",
                "status": "recommended",
            },
            {
                "action": f"Check alternative supplier {alternatives[0] if alternatives else 'SUP-004'}",
                "agent": "graphrag",
                "permission": "procurement_manager",
                "status": "recommended",
            },
            {
                "action": "Query delivery status via MCP",
                "agent": "tool_node",
                "permission": "logistics_manager",
                "status": "optional",
                "tool_name": "query_delivery_status",
            },
            {
                "action": "Generate risk report (approval required)",
                "agent": "tool_node",
                "permission": "executive",
                "status": "approval_required",
                "tool_name": "export_risk_report",
            },
        ]

    impacted_paths = [
        {
            "path_index": path.path_index,
            "path_text": path.path_text,
            "hop_count": len(path.nodes) - 1 if path.nodes else 0,
            "template_id": path.template_id,
            "graph_path_ref": f"{path.template_id}#path_{path.path_index}",
        }
        for path in result.graph_paths
    ]

    await session.commit()

    return {
        "risk_source": {
            "node_type": payload.source_node_type,
            "node_code": code,
            "risk_type": payload.risk_type,
            "severity": payload.severity,
        },
        "impacted_paths": impacted_paths,
        "affected_suppliers": result.affected_suppliers,
        "affected_materials": result.affected_materials,
        "affected_products": result.affected_products,
        "affected_orders": result.affected_orders,
        "affected_customers": result.affected_customers,
        "alternative_suppliers": alternatives,
        "alternative_paths": alt_paths,
        "graph_paths": [
            {
                "path_index": p.path_index,
                "path_text": p.path_text,
                "nodes": [n.to_dict() for n in p.nodes],
                "relationships": [r.to_dict() for r in p.relationships],
                "template_id": p.template_id,
            }
            for p in result.graph_paths
        ],
        "query_type": result.query_type,
        "cypher_template": result.cypher_template,
        "latency_ms": result.latency_ms,
        "trace_id": trace_id,
        "permission_decision": result.permission_decision,
        "agent_actions": agent_actions,
        "impact_summary": {
            "total_paths": len(impacted_paths),
            "entities_affected": (
                len(result.affected_suppliers)
                + len(result.affected_materials)
                + len(result.affected_products)
                + len(result.affected_orders)
                + len(result.affected_customers)
            ),
            "severity": payload.severity,
        },
    }
