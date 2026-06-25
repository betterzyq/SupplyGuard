"""Template-based Cypher queries for GraphRAG.

TODO: Text2Cypher is intentionally not implemented in MVP GraphRAG phase.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.graphrag.graph_schema import QUERY_TYPES


@dataclass(frozen=True)
class CypherTemplate:
    query_type: str
    description: str
    cypher: str
    requires_entity_code: bool = True


TEMPLATES: dict[str, CypherTemplate] = {
    "supplier_impact": CypherTemplate(
        query_type="supplier_impact",
        description="Supplier delay/risk impact on materials, products, orders, customers",
        cypher="""
        MATCH (s:Supplier {tenant_id: $tenant_id, code: $entity_code})
        WHERE $supplier_scope IS NULL OR s.code = $supplier_scope
        OPTIONAL MATCH path = (s)-[:SUPPLIES]->(m:Material)-[:USED_IN]->(p:Product)
            -[:ORDERED_IN]->(o:Order)-[:FOR_CUSTOMER]->(c:Customer)
        WHERE path IS NULL OR ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)
        RETURN path
        LIMIT $limit
        """,
    ),
    "supplier_impact_extended": CypherTemplate(
        query_type="supplier_impact_extended",
        description="Extended supplier impact via FULFILLS, risk and delivery edges",
        cypher="""
        MATCH (s:Supplier {tenant_id: $tenant_id, code: $entity_code})
        WHERE $supplier_scope IS NULL OR s.code = $supplier_scope
        OPTIONAL MATCH (s)-[:FULFILLS]->(o:Order)
        WHERE o.tenant_id = $tenant_id
        OPTIONAL MATCH (p:Product)-[:ORDERED_IN]->(o)
        OPTIONAL MATCH (o)-[:FOR_CUSTOMER]->(c:Customer)
        OPTIONAL MATCH (s)-[:HAS_RISK_EVENT]->(r:RiskEvent)
        OPTIONAL MATCH (s)-[:HAS_DELIVERY_EVENT]->(d:DeliveryEvent)
        RETURN s,
            collect(DISTINCT o) AS orders,
            collect(DISTINCT p) AS products,
            collect(DISTINCT c) AS customers,
            collect(DISTINCT r) AS risks,
            collect(DISTINCT d) AS deliveries
        LIMIT $limit
        """,
    ),
    "product_dependency": CypherTemplate(
        query_type="product_dependency",
        description="Product dependency on materials and suppliers",
        cypher="""
        MATCH (p:Product {tenant_id: $tenant_id, code: $entity_code})
        OPTIONAL MATCH path = (s:Supplier)-[:SUPPLIES]->(m:Material)-[:USED_IN]->(p)
        WHERE path IS NULL OR (
            ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)
            AND ($supplier_scope IS NULL OR s.code = $supplier_scope)
        )
        RETURN path
        LIMIT $limit
        """,
    ),
    "supplier_alternatives": CypherTemplate(
        query_type="supplier_alternatives",
        description="Alternative suppliers for a given supplier",
        cypher="""
        MATCH (s:Supplier {tenant_id: $tenant_id, code: $entity_code})
        OPTIONAL MATCH (s)-[r:ALTERNATIVE_TO]->(alt:Supplier)
        WHERE alt.tenant_id = $tenant_id
        AND ($supplier_scope IS NULL OR s.code = $supplier_scope)
        RETURN s, collect(DISTINCT alt) AS alternatives, collect(DISTINCT r) AS rels
        LIMIT $limit
        """,
    ),
    "delivery_delay_impact": CypherTemplate(
        query_type="delivery_delay_impact",
        description="Delivery delays and impacted orders",
        cypher="""
        MATCH (s:Supplier {tenant_id: $tenant_id})-[:HAS_DELIVERY_EVENT]->(d:DeliveryEvent)
        WHERE d.tenant_id = $tenant_id AND d.delay_days > 0
        AND ($entity_code IS NULL OR s.code = $entity_code)
        AND ($supplier_scope IS NULL OR s.code = $supplier_scope)
        OPTIONAL MATCH (s)-[:SUPPLIES]->(:Material)-[:USED_IN]->(:Product)
            -[:ORDERED_IN]->(o:Order)
        WHERE o.tenant_id = $tenant_id
        RETURN s, d, collect(DISTINCT o) AS orders
        ORDER BY d.delay_days DESC
        LIMIT $limit
        """,
        requires_entity_code=False,
    ),
    "delivery_delay_impact_by_order": CypherTemplate(
        query_type="delivery_delay_impact_by_order",
        description="Order delivery delay and downstream/upstream impact",
        cypher="""
        MATCH (o:Order {tenant_id: $tenant_id})
        WHERE $entity_code IS NOT NULL AND (o.code = $entity_code OR o.order_no = $entity_code)
        OPTIONAL MATCH (p:Product)-[:ORDERED_IN]->(o)
        OPTIONAL MATCH (m:Material)-[:USED_IN]->(p)
        OPTIONAL MATCH (s:Supplier)-[:SUPPLIES]->(m)
        WHERE s IS NULL OR ($supplier_scope IS NULL OR s.code = $supplier_scope)
        OPTIONAL MATCH (o)-[:FOR_CUSTOMER]->(c:Customer)
        OPTIONAL MATCH (d:DeliveryEvent {tenant_id: $tenant_id})
        WHERE d.order_no = o.code OR d.order_no = o.order_no
        RETURN o,
            collect(DISTINCT p) AS products,
            collect(DISTINCT m) AS materials,
            collect(DISTINCT s) AS suppliers,
            collect(DISTINCT d) AS deliveries,
            collect(DISTINCT c) AS customers
        LIMIT $limit
        """,
        requires_entity_code=True,
    ),
    "quality_issue_trace": CypherTemplate(
        query_type="quality_issue_trace",
        description="Quality issue trace to products and materials",
        cypher="""
        MATCH (qi:QualityIssue {tenant_id: $tenant_id})
        WHERE ($entity_code IS NULL OR qi.id = $entity_code OR qi.code = $entity_code)
        MATCH (s:Supplier {tenant_id: $tenant_id})-[:HAS_QUALITY_ISSUE]->(qi)
        WHERE $supplier_scope IS NULL OR s.code = $supplier_scope
        OPTIONAL MATCH path = (s)-[:SUPPLIES]->(m:Material)-[:USED_IN]->(p:Product)
        WHERE path IS NULL OR ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)
        RETURN qi, s, path
        LIMIT $limit
        """,
        requires_entity_code=False,
    ),
    "customer_order_dependency": CypherTemplate(
        query_type="customer_order_dependency",
        description="Customer orders and upstream supplier dependencies",
        cypher="""
        MATCH (c:Customer {tenant_id: $tenant_id, code: $entity_code})
        OPTIONAL MATCH path = (c)<-[:FOR_CUSTOMER]-(o:Order)<-[:ORDERED_IN]-(p:Product)
            <-[:USED_IN]-(m:Material)<-[:SUPPLIES]-(s:Supplier)
        WHERE path IS NULL OR (
            ALL(n IN nodes(path) WHERE n.tenant_id = $tenant_id)
            AND ($supplier_scope IS NULL OR s.code = $supplier_scope)
        )
        RETURN path
        LIMIT $limit
        """,
    ),
}


def get_template(query_type: str) -> CypherTemplate:
    if query_type not in QUERY_TYPES:
        raise ValueError(f"Unsupported query_type: {query_type}")
    return TEMPLATES[query_type]


def build_parameters(
    *,
    tenant_id: str,
    entity_code: str | None,
    limit: int,
    supplier_scope: str | None,
) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "entity_code": entity_code,
        "limit": limit,
        "supplier_scope": supplier_scope,
    }
