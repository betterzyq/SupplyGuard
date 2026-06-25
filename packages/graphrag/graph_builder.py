"""Build and upsert supply chain graph in Neo4j."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.graphrag.graph_schema import CONSTRAINTS
from packages.graphrag.neo4j_client import run_cypher, run_write


def _metadata_value(metadata: dict[str, Any] | None) -> str:
    return json.dumps(metadata or {}, ensure_ascii=False)


async def ensure_constraints() -> None:
    for statement in CONSTRAINTS:
        await run_write(statement)


async def upsert_supplier(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:Supplier {tenant_id: $tenant_id, code: $code})
        SET n.id = $id,
            n.name = $name,
            n.country = $country,
            n.tier = $tier,
            n.risk_score = $risk_score,
            n.status = $status,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "code": data["code"],
            "id": data.get("id") or data["code"],
            "name": data["name"],
            "country": data.get("country", ""),
            "tier": int(data.get("tier", 1)),
            "risk_score": float(data.get("risk_score", 0)),
            "status": data.get("status", "active"),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_material(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:Material {tenant_id: $tenant_id, code: $code})
        SET n.id = $id,
            n.name = $name,
            n.category = $category,
            n.is_critical = $is_critical,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "code": data["code"],
            "id": data.get("id") or data["code"],
            "name": data["name"],
            "category": data.get("category", ""),
            "is_critical": bool(data.get("is_critical", False)),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_product(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:Product {tenant_id: $tenant_id, code: $code})
        SET n.id = $id,
            n.name = $name,
            n.category = $category,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "code": data["code"],
            "id": data.get("id") or data["code"],
            "name": data["name"],
            "category": data.get("category", ""),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_customer(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:Customer {tenant_id: $tenant_id, code: $code})
        SET n.id = $id,
            n.name = $name,
            n.region = $region,
            n.tier = $tier,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "code": data["code"],
            "id": data.get("id") or data["code"],
            "name": data["name"],
            "region": data.get("region", ""),
            "tier": int(data.get("tier", 1)),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_order(tenant_id: str, data: dict[str, Any]) -> None:
    code = data.get("code") or data["order_no"]
    await run_write(
        """
        MERGE (n:Order {tenant_id: $tenant_id, code: $code})
        SET n.id = $id,
            n.order_no = $order_no,
            n.name = $name,
            n.status = $status,
            n.expected_delivery_date = $expected_delivery_date,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "code": code,
            "id": data.get("id") or code,
            "order_no": data["order_no"],
            "name": data.get("name") or data["order_no"],
            "status": data.get("status", "open"),
            "expected_delivery_date": data.get("expected_delivery_date"),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_risk_event(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:RiskEvent {tenant_id: $tenant_id, id: $id})
        SET n.code = $code,
            n.name = $name,
            n.event_type = $event_type,
            n.severity = $severity,
            n.title = $title,
            n.detected_at = $detected_at,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "id": data["id"],
            "code": data.get("code") or data["id"],
            "name": data.get("title") or data["id"],
            "event_type": data["event_type"],
            "severity": data["severity"],
            "title": data["title"],
            "detected_at": data.get("detected_at"),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_delivery_event(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:DeliveryEvent {tenant_id: $tenant_id, id: $id})
        SET n.code = $code,
            n.name = $name,
            n.status = $status,
            n.delay_days = $delay_days,
            n.delay_reason = $delay_reason,
            n.order_no = $order_no,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "id": data["id"],
            "code": data["id"],
            "name": data["id"],
            "status": data.get("status", ""),
            "delay_days": int(data.get("delay_days") or 0),
            "delay_reason": data.get("delay_reason"),
            "order_no": data.get("order_no"),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def upsert_quality_issue(tenant_id: str, data: dict[str, Any]) -> None:
    await run_write(
        """
        MERGE (n:QualityIssue {tenant_id: $tenant_id, id: $id})
        SET n.code = $code,
            n.name = $name,
            n.defect_type = $defect_type,
            n.severity = $severity,
            n.result = $result,
            n.metadata = $metadata
        """,
        {
            "tenant_id": tenant_id,
            "id": data["id"],
            "code": data["id"],
            "name": data["id"],
            "defect_type": data.get("defect_type", ""),
            "severity": data.get("severity", ""),
            "result": data.get("result", ""),
            "metadata": _metadata_value(data.get("metadata")),
        },
    )


async def merge_relationship(
    tenant_id: str,
    start_label: str,
    start_key: str,
    start_value: str,
    rel_type: str,
    end_label: str,
    end_key: str,
    end_value: str,
    *,
    rel_props: dict[str, Any] | None = None,
) -> None:
    rel_props = rel_props or {}
    await run_write(
        f"""
        MATCH (a:{start_label} {{tenant_id: $tenant_id, {start_key}: $start_value}})
        MATCH (b:{end_label} {{tenant_id: $tenant_id, {end_key}: $end_value}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET r += $rel_props
        """,
        {
            "tenant_id": tenant_id,
            "start_value": start_value,
            "end_value": end_value,
            "rel_props": rel_props,
        },
    )


async def count_graph_stats(tenant_id: str) -> dict[str, int]:
    rows = await run_cypher(
        """
        MATCH (n {tenant_id: $tenant_id})
        WITH labels(n)[0] AS label, count(*) AS cnt
        RETURN label, cnt
        """,
        {"tenant_id": tenant_id},
    )
    rel_rows = await run_cypher(
        """
        MATCH ()-[r]->()
        WHERE startNode(r).tenant_id = $tenant_id
        RETURN count(r) AS relationship_count
        """,
        {"tenant_id": tenant_id},
    )
    stats = {row["label"]: row["cnt"] for row in rows}
    stats["relationship_count"] = rel_rows[0]["relationship_count"] if rel_rows else 0
    return {
        "supplier_count": stats.get("Supplier", 0),
        "material_count": stats.get("Material", 0),
        "product_count": stats.get("Product", 0),
        "order_count": stats.get("Order", 0),
        "customer_count": stats.get("Customer", 0),
        "relationship_count": stats.get("relationship_count", 0),
    }


def load_graph_seed(seed_path: Path | None = None) -> dict[str, Any]:
    path = seed_path or Path(__file__).resolve().parents[2] / "data" / "seed" / "graph_seed.json"
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
