"""Template-based graph retriever."""

from __future__ import annotations

import time
import uuid
from typing import Any

from neo4j.graph import Node, Path, Relationship
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.audit import write_audit_log
from packages.authz.rbac import PermissionDecision, UserContext
from packages.common.db.models.supplier import Supplier
from packages.graphrag.cypher_templates import TEMPLATES, build_parameters, get_template
from packages.graphrag.graph_context import GraphNode, GraphPath, GraphRetrievalResult, GraphRelationship
from packages.graphrag.graph_permissions import check_graph_query_permission, resolve_supplier_scope
from packages.graphrag.neo4j_client import run_cypher
from packages.observability.repositories.graph_retrieval_log_repo import write_graph_retrieval_log


def _node_label(node: Node) -> str:
    return list(node.labels)[0] if node.labels else "Unknown"


def _node_code(node: Node) -> str:
    props = dict(node)
    return str(props.get("code") or props.get("id") or "")


def _node_name(node: Node) -> str:
    props = dict(node)
    return str(props.get("name") or props.get("title") or _node_code(node))


def _path_to_graph_path(path: Path, template_id: str, path_index: int) -> GraphPath:
    nodes: list[GraphNode] = []
    relationships: list[GraphRelationship] = []
    parts: list[str] = []

    for node in path.nodes:
        label = _node_label(node)
        code = _node_code(node)
        name = _node_name(node)
        nodes.append(GraphNode(label=label, code=code, name=name, properties=dict(node)))
        parts.append(f"{label} {code}")

    for rel in path.relationships:
        start = _node_code(rel.start_node)
        end = _node_code(rel.end_node)
        relationships.append(
            GraphRelationship(type=rel.type, start_code=start, end_code=end, properties=dict(rel))
        )

    path_text = " → ".join(parts)
    return GraphPath(
        path_index=path_index,
        path_text=path_text,
        nodes=nodes,
        relationships=relationships,
        template_id=template_id,
    )


def _collect_affected(paths: list[GraphPath]) -> dict[str, list[str]]:
    suppliers: set[str] = set()
    materials: set[str] = set()
    products: set[str] = set()
    orders: set[str] = set()
    customers: set[str] = set()

    for path in paths:
        for node in path.nodes:
            if node.label == "Supplier":
                suppliers.add(node.code)
            elif node.label == "Material":
                materials.add(node.code)
            elif node.label == "Product":
                products.add(node.code)
            elif node.label == "Order":
                orders.add(node.code)
            elif node.label == "Customer":
                customers.add(node.code)

    return {
        "affected_suppliers": sorted(suppliers),
        "affected_materials": sorted(materials),
        "affected_products": sorted(products),
        "affected_orders": sorted(orders),
        "affected_customers": sorted(customers),
    }


def _parse_alternatives(records: list[dict[str, Any]], template_id: str) -> list[GraphPath]:
    paths: list[GraphPath] = []
    for row in records:
        source = row.get("s")
        alternatives = row.get("alternatives") or []
        if source is None:
            continue
        source_code = _node_code(source)
        if not alternatives:
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Supplier {source_code} has no registered alternatives",
                    nodes=[GraphNode(_node_label(source), source_code, _node_name(source), dict(source))],
                    relationships=[],
                    template_id=template_id,
                )
            )
            continue
        for alt in alternatives:
            if alt is None:
                continue
            alt_code = _node_code(alt)
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Supplier {source_code} → ALTERNATIVE_TO → Supplier {alt_code}",
                    nodes=[
                        GraphNode(_node_label(source), source_code, _node_name(source), dict(source)),
                        GraphNode(_node_label(alt), alt_code, _node_name(alt), dict(alt)),
                    ],
                    relationships=[
                        GraphRelationship("ALTERNATIVE_TO", source_code, alt_code),
                    ],
                    template_id=template_id,
                )
            )
    return paths


def _parse_delivery_delay(records: list[dict[str, Any]], template_id: str) -> list[GraphPath]:
    paths: list[GraphPath] = []
    for row in records:
        supplier = row.get("s")
        delivery = row.get("d")
        orders = row.get("orders") or []
        if supplier is None or delivery is None:
            continue
        supplier_code = _node_code(supplier)
        delivery_code = _node_code(delivery)
        if not orders:
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Supplier {supplier_code} → DeliveryEvent {delivery_code}",
                    nodes=[
                        GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier)),
                        GraphNode("DeliveryEvent", delivery_code, delivery_code, dict(delivery)),
                    ],
                    relationships=[GraphRelationship("HAS_DELIVERY_EVENT", supplier_code, delivery_code)],
                    template_id=template_id,
                )
            )
            continue
        for order in orders:
            if order is None:
                continue
            order_code = _node_code(order)
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=(
                        f"Supplier {supplier_code} → DeliveryEvent {delivery_code} "
                        f"→ Order {order_code}"
                    ),
                    nodes=[
                        GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier)),
                        GraphNode("DeliveryEvent", delivery_code, delivery_code, dict(delivery)),
                        GraphNode("Order", order_code, _node_name(order), dict(order)),
                    ],
                    relationships=[
                        GraphRelationship("HAS_DELIVERY_EVENT", supplier_code, delivery_code),
                    ],
                    template_id=template_id,
                )
            )
    return paths


def _parse_supplier_impact_extended(records: list[dict[str, Any]], template_id: str) -> list[GraphPath]:
    paths: list[GraphPath] = []
    for row in records:
        supplier = row.get("s")
        if supplier is None:
            continue
        supplier_code = _node_code(supplier)
        orders = [o for o in (row.get("orders") or []) if o is not None]
        products = [p for p in (row.get("products") or []) if p is not None]
        customers = [c for c in (row.get("customers") or []) if c is not None]
        risks = [r for r in (row.get("risks") or []) if r is not None]
        deliveries = [d for d in (row.get("deliveries") or []) if d is not None]

        if not orders and not risks and not deliveries:
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=(
                        f"Supplier {supplier_code} exists but has no orders/risk/delivery edges in Neo4j. "
                        "Run: make build-real-graph -- --reset-graph"
                    ),
                    nodes=[GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier))],
                    relationships=[],
                    template_id=template_id,
                )
            )
            continue

        for risk in risks:
            risk_code = _node_code(risk)
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Supplier {supplier_code} → RiskEvent {risk_code}",
                    nodes=[
                        GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier)),
                        GraphNode("RiskEvent", risk_code, _node_name(risk), dict(risk)),
                    ],
                    relationships=[GraphRelationship("HAS_RISK_EVENT", supplier_code, risk_code)],
                    template_id=template_id,
                )
            )

        for delivery in deliveries:
            delivery_code = _node_code(delivery)
            delay_days = dict(delivery).get("delay_days", 0)
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Supplier {supplier_code} → DeliveryEvent {delivery_code} (delay {delay_days}d)",
                    nodes=[
                        GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier)),
                        GraphNode("DeliveryEvent", delivery_code, delivery_code, dict(delivery)),
                    ],
                    relationships=[GraphRelationship("HAS_DELIVERY_EVENT", supplier_code, delivery_code)],
                    template_id=template_id,
                )
            )

        for order in orders:
            order_code = _node_code(order)
            product = products[0] if products else None
            customer = customers[0] if customers else None
            nodes = [
                GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier)),
                GraphNode("Order", order_code, _node_name(order), dict(order)),
            ]
            parts = [f"Supplier {supplier_code}", f"Order {order_code}"]
            rels = [GraphRelationship("FULFILLS", supplier_code, order_code)]
            if product is not None:
                product_code = _node_code(product)
                nodes.insert(1, GraphNode("Product", product_code, _node_name(product), dict(product)))
                parts.insert(1, f"Product {product_code}")
            if customer is not None:
                customer_code = _node_code(customer)
                nodes.append(GraphNode("Customer", customer_code, _node_name(customer), dict(customer)))
                parts.append(f"Customer {customer_code}")
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=" → ".join(parts),
                    nodes=nodes,
                    relationships=rels,
                    template_id=template_id,
                )
            )
    return paths


def _parse_order_delivery_impact(records: list[dict[str, Any]], template_id: str) -> list[GraphPath]:
    paths: list[GraphPath] = []
    for row in records:
        order = row.get("o")
        if order is None:
            continue
        order_code = _node_code(order)
        products = [p for p in (row.get("products") or []) if p is not None]
        materials = [m for m in (row.get("materials") or []) if m is not None]
        suppliers = [s for s in (row.get("suppliers") or []) if s is not None]
        deliveries = [d for d in (row.get("deliveries") or []) if d is not None]
        customers = [c for c in (row.get("customers") or []) if c is not None]

        if not products and not deliveries and not customers:
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Order {order_code} has no linked downstream entities",
                    nodes=[GraphNode("Order", order_code, _node_name(order), dict(order))],
                    relationships=[],
                    template_id=template_id,
                )
            )
            continue

        for delivery in deliveries:
            delivery_code = _node_code(delivery)
            delay_days = dict(delivery).get("delay_days", 0)
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"Order {order_code} → DeliveryEvent {delivery_code} (delay {delay_days}d)",
                    nodes=[
                        GraphNode("Order", order_code, _node_name(order), dict(order)),
                        GraphNode("DeliveryEvent", delivery_code, delivery_code, dict(delivery)),
                    ],
                    relationships=[GraphRelationship("HAS_DELIVERY_EVENT", order_code, delivery_code)],
                    template_id=template_id,
                )
            )

        for product in products:
            product_code = _node_code(product)
            for customer in customers or [None]:
                nodes: list[GraphNode] = [
                    GraphNode("Order", order_code, _node_name(order), dict(order)),
                    GraphNode("Product", product_code, _node_name(product), dict(product)),
                ]
                rels: list[GraphRelationship] = []
                parts = [f"Order {order_code}", f"Product {product_code}"]
                if customer is not None:
                    customer_code = _node_code(customer)
                    nodes.append(GraphNode("Customer", customer_code, _node_name(customer), dict(customer)))
                    parts.append(f"Customer {customer_code}")
                paths.append(
                    GraphPath(
                        path_index=len(paths) + 1,
                        path_text=" → ".join(parts),
                        nodes=nodes,
                        relationships=rels,
                        template_id=template_id,
                    )
                )

            if suppliers and materials:
                supplier = suppliers[0]
                material = materials[0]
                supplier_code = _node_code(supplier)
                material_code = _node_code(material)
                paths.append(
                    GraphPath(
                        path_index=len(paths) + 1,
                        path_text=(
                            f"Supplier {supplier_code} → Material {material_code} "
                            f"→ Product {product_code} → Order {order_code}"
                        ),
                        nodes=[
                            GraphNode("Supplier", supplier_code, _node_name(supplier), dict(supplier)),
                            GraphNode("Material", material_code, _node_name(material), dict(material)),
                            GraphNode("Product", product_code, _node_name(product), dict(product)),
                            GraphNode("Order", order_code, _node_name(order), dict(order)),
                        ],
                        relationships=[
                            GraphRelationship("SUPPLIES", supplier_code, material_code),
                            GraphRelationship("USED_IN", material_code, product_code),
                        ],
                        template_id=template_id,
                    )
                )
    return paths


async def _is_order_entity(tenant_id: str, entity_code: str) -> bool:
    rows = await run_cypher(
        """
        MATCH (o:Order {tenant_id: $tenant_id})
        WHERE o.code = $entity_code OR o.order_no = $entity_code
        RETURN o LIMIT 1
        """,
        {"tenant_id": tenant_id, "entity_code": entity_code},
    )
    return bool(rows)


def _parse_quality_trace(records: list[dict[str, Any]], template_id: str) -> list[GraphPath]:
    paths: list[GraphPath] = []
    for row in records:
        path = row.get("path")
        qi = row.get("qi")
        if path is not None:
            paths.append(_path_to_graph_path(path, template_id, len(paths) + 1))
        elif qi is not None:
            qi_code = _node_code(qi)
            paths.append(
                GraphPath(
                    path_index=len(paths) + 1,
                    path_text=f"QualityIssue {qi_code}",
                    nodes=[GraphNode("QualityIssue", qi_code, qi_code, dict(qi))],
                    relationships=[],
                    template_id=template_id,
                )
            )
    return paths


async def resolve_supplier_code(
    session: AsyncSession | None,
    user_context: UserContext,
) -> str | None:
    if not user_context.is_external_supplier or not user_context.supplier_id or session is None:
        return None
    result = await session.execute(
        select(Supplier.code).where(
            Supplier.id == user_context.supplier_id,
            Supplier.tenant_id == user_context.tenant_id,
        )
    )
    return result.scalar_one_or_none()


async def execute_graph_query(
    user_context: UserContext,
    *,
    query: str,
    query_type: str,
    entity_code: str | None = None,
    top_k: int = 20,
    trace_id: str | None = None,
    agent_run_id: uuid.UUID | None = None,
    session: AsyncSession | None = None,
    ip_address: str | None = None,
) -> GraphRetrievalResult:
    started = time.perf_counter()
    trace_id = trace_id or str(uuid.uuid4())
    tenant_id = str(user_context.tenant_id)

    supplier_scope = await resolve_supplier_code(session, user_context)
    if user_context.is_external_supplier and not entity_code and supplier_scope:
        entity_code = supplier_scope

    permission = check_graph_query_permission(
        user_context,
        query_type,
        supplier_code=entity_code,
        resolved_supplier_scope=supplier_scope,
    )

    if not permission.allowed:
        if session is not None:
            await write_audit_log(
                session,
                tenant_id=user_context.tenant_id,
                user_id=user_context.user_id,
                trace_id=trace_id,
                action="graph_query_denied",
                resource_type="graphrag",
                resource_id=trace_id,
                permission_decision="denied",
                reason=permission.reason,
                ip_address=ip_address,
                metadata={"query_type": query_type, "entity_code": entity_code},
            )
            await write_graph_retrieval_log(
                session,
                tenant_id=user_context.tenant_id,
                user_id=user_context.user_id,
                trace_id=trace_id,
                query=query,
                query_type=query_type,
                cypher_template=query_type,
                cypher_query="",
                parameters={},
                paths_found=[],
                result_count=0,
                latency_ms=int((time.perf_counter() - started) * 1000),
                permission_decision="denied",
                error_message=permission.reason,
                agent_run_id=agent_run_id,
            )
        return GraphRetrievalResult(
            query=query,
            query_type=query_type,
            matched_entities=[],
            graph_paths=[],
            affected_suppliers=[],
            affected_materials=[],
            affected_products=[],
            affected_orders=[],
            affected_customers=[],
            cypher_template=query_type,
            cypher_query="",
            parameters={},
            trace_id=trace_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
            result_count=0,
            permission_decision="denied",
            error_message=permission.reason,
        )

    template = get_template(query_type)
    if template.requires_entity_code and not entity_code:
        raise ValueError(f"query_type={query_type} requires entity_code")

    effective_scope = supplier_scope if user_context.is_external_supplier else None
    parameters = build_parameters(
        tenant_id=tenant_id,
        entity_code=entity_code,
        limit=top_k,
        supplier_scope=effective_scope,
    )

    order_delivery_mode = False
    if query_type == "delivery_delay_impact" and entity_code:
        order_delivery_mode = await _is_order_entity(tenant_id, entity_code)

    if order_delivery_mode:
        order_template = TEMPLATES["delivery_delay_impact_by_order"]
        cypher = " ".join(order_template.cypher.split())
    else:
        cypher = " ".join(template.cypher.split())

    records = await run_cypher(cypher, parameters)

    if query_type == "supplier_alternatives":
        graph_paths = _parse_alternatives(records, query_type)
    elif query_type == "delivery_delay_impact" and order_delivery_mode:
        graph_paths = _parse_order_delivery_impact(records, query_type)
    elif query_type == "delivery_delay_impact":
        graph_paths = _parse_delivery_delay(records, query_type)
    elif query_type == "quality_issue_trace":
        graph_paths = _parse_quality_trace(records, query_type)
    else:
        graph_paths = []
        for row in records:
            path = row.get("path")
            if path is not None:
                graph_paths.append(_path_to_graph_path(path, query_type, len(graph_paths) + 1))

    if query_type == "supplier_impact" and not graph_paths and entity_code:
        ext_cypher = " ".join(TEMPLATES["supplier_impact_extended"].cypher.split())
        ext_records = await run_cypher(ext_cypher, parameters)
        graph_paths = _parse_supplier_impact_extended(ext_records, query_type)
        if graph_paths:
            cypher = ext_cypher

    affected = _collect_affected(graph_paths)
    latency_ms = int((time.perf_counter() - started) * 1000)
    paths_payload = [path.to_dict() for path in graph_paths]

    if session is not None:
        await write_graph_retrieval_log(
            session,
            tenant_id=user_context.tenant_id,
            user_id=user_context.user_id,
            trace_id=trace_id,
            query=query,
            query_type=query_type,
            cypher_template=query_type,
            cypher_query=cypher,
            parameters=parameters,
            paths_found=paths_payload,
            result_count=len(graph_paths),
            latency_ms=latency_ms,
            permission_decision="allowed",
            agent_run_id=agent_run_id,
        )

    matched_entities: list[dict[str, Any]] = []
    if entity_code:
        matched_entities.append({"code": entity_code, "query_type": query_type})

    return GraphRetrievalResult(
        query=query,
        query_type=query_type,
        matched_entities=matched_entities,
        graph_paths=graph_paths,
        **affected,
        cypher_template=query_type,
        cypher_query=cypher,
        parameters=parameters,
        trace_id=trace_id,
        latency_ms=latency_ms,
        result_count=len(graph_paths),
        permission_decision="allowed",
    )
