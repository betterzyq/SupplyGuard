#!/usr/bin/env python3
"""Build supply chain graph from PostgreSQL seed + graph_seed.json."""

from __future__ import annotations

import asyncio
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from packages.common.db.models.order import Order
from packages.common.db.models.risk_event import RiskEvent
from packages.common.db.models.supplier import Supplier
from packages.common.db.models.tenant import Tenant
from packages.common.db.session import get_session_factory
from packages.graphrag.graph_builder import (
    count_graph_stats,
    ensure_constraints,
    load_graph_seed,
    merge_relationship,
    upsert_customer,
    upsert_delivery_event,
    upsert_material,
    upsert_order,
    upsert_product,
    upsert_quality_issue,
    upsert_risk_event,
    upsert_supplier,
)


async def build_graph() -> dict[str, int]:
    seed_data = load_graph_seed()
    session_factory = get_session_factory()

    async with session_factory() as session:
        tenant = (await session.execute(select(Tenant).where(Tenant.code == "demo-mfg"))).scalar_one()
        tenant_id = str(tenant.id)

        suppliers = (
            await session.execute(select(Supplier).where(Supplier.tenant_id == tenant.id))
        ).scalars().all()
        orders = (
            await session.execute(select(Order).where(Order.tenant_id == tenant.id))
        ).scalars().all()
        risk_events = (
            await session.execute(select(RiskEvent).where(RiskEvent.tenant_id == tenant.id))
        ).scalars().all()

    await ensure_constraints()

    for supplier in suppliers:
        await upsert_supplier(
            tenant_id,
            {
                "id": str(supplier.id),
                "code": supplier.code,
                "name": supplier.name,
                "country": supplier.country,
                "tier": supplier.tier,
                "risk_score": float(supplier.risk_score),
                "status": supplier.status,
                "metadata": supplier.metadata_ or {},
            },
        )

    for material in seed_data["materials"]:
        await upsert_material(tenant_id, material)

    for product in seed_data["products"]:
        await upsert_product(tenant_id, product)

    for customer in seed_data["customers"]:
        await upsert_customer(tenant_id, customer)

    order_status_by_no = {order.order_no: order.status for order in orders}
    order_delivery_by_no = {
        order.order_no: order.expected_delivery_date.isoformat()
        if isinstance(order.expected_delivery_date, date)
        else order.expected_delivery_date
        for order in orders
    }

    for order in orders:
        await upsert_order(
            tenant_id,
            {
                "id": str(order.id),
                "code": order.order_no,
                "order_no": order.order_no,
                "name": order.order_no,
                "status": order.status,
                "expected_delivery_date": order_delivery_by_no.get(order.order_no),
                "metadata": {"product_name": order.product_name, "customer_name": order.customer_name},
            },
        )

    for risk in risk_events:
        await upsert_risk_event(
            tenant_id,
            {
                "id": str(risk.id),
                "event_type": risk.event_type,
                "severity": risk.severity,
                "title": risk.title,
                "detected_at": risk.detected_at.isoformat() if risk.detected_at else None,
                "metadata": {"description": risk.description, "source": risk.source},
            },
        )
        supplier = next((item for item in suppliers if item.id == risk.supplier_id), None)
        if supplier:
            await merge_relationship(
                tenant_id,
                "Supplier",
                "code",
                supplier.code,
                "HAS_RISK_EVENT",
                "RiskEvent",
                "id",
                str(risk.id),
            )

    for link in seed_data["supplies"]:
        await merge_relationship(
            tenant_id,
            "Supplier",
            "code",
            link["supplier_code"],
            "SUPPLIES",
            "Material",
            "code",
            link["material_code"],
        )

    for link in seed_data["used_in"]:
        await merge_relationship(
            tenant_id,
            "Material",
            "code",
            link["material_code"],
            "USED_IN",
            "Product",
            "code",
            link["product_code"],
        )

    for link in seed_data["order_links"]:
        await merge_relationship(
            tenant_id,
            "Product",
            "code",
            link["product_code"],
            "ORDERED_IN",
            "Order",
            "code",
            link["order_no"],
        )
        await merge_relationship(
            tenant_id,
            "Order",
            "code",
            link["order_no"],
            "FOR_CUSTOMER",
            "Customer",
            "code",
            link["customer_code"],
        )

    for alt in seed_data["alternatives"]:
        await merge_relationship(
            tenant_id,
            "Supplier",
            "code",
            alt["supplier_code"],
            "ALTERNATIVE_TO",
            "Supplier",
            "code",
            alt["alternative_code"],
            rel_props={"similarity_score": alt.get("similarity_score")},
        )

    for event in seed_data["delivery_events"]:
        await upsert_delivery_event(tenant_id, event)
        await merge_relationship(
            tenant_id,
            "Supplier",
            "code",
            event["supplier_code"],
            "HAS_DELIVERY_EVENT",
            "DeliveryEvent",
            "id",
            event["id"],
        )

    for issue in seed_data["quality_issues"]:
        await upsert_quality_issue(tenant_id, issue)
        await merge_relationship(
            tenant_id,
            "Supplier",
            "code",
            issue["supplier_code"],
            "HAS_QUALITY_ISSUE",
            "QualityIssue",
            "id",
            issue["id"],
        )

    stats = await count_graph_stats(tenant_id)
    print("Graph build completed:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return stats


def main() -> None:
    asyncio.run(build_graph())


if __name__ == "__main__":
    main()
