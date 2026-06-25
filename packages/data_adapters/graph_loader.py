"""Build Neo4j supply chain graph from normalized real-data CSVs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from packages.graphrag.graph_builder import (
    count_graph_stats,
    ensure_constraints,
    merge_relationship,
    upsert_customer,
    upsert_delivery_event,
    upsert_material,
    upsert_order,
    upsert_product,
    upsert_risk_event,
    upsert_supplier,
)
from packages.graphrag.neo4j_client import run_write
from packages.data_adapters.merger import link_scms_suppliers_to_graph
from packages.data_adapters.schema import NormalizedDataset


def _read_csv(normalized_dir: Path, name: str) -> pd.DataFrame:
    path = normalized_dir / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def _meta(row: pd.Series, extra: dict | None = None) -> dict[str, Any]:
    base = {
        "real_data": True,
        "source_dataset": row.get("source_dataset"),
    }
    if extra:
        base.update(extra)
    return {k: v for k, v in base.items() if v is not None and not (isinstance(v, float) and pd.isna(v))}


def _select_orders_for_graph(orders: pd.DataFrame, limit: int | None) -> pd.DataFrame:
    """Keep primary slice plus SCMS orders so real suppliers are not orphaned."""
    if orders.empty or not limit or len(orders) <= limit:
        return orders

    primary = orders.head(limit).copy()
    selected_ids = set(primary["order_id"].astype(str))

    if "source_dataset" not in orders.columns:
        return primary

    scms = orders[orders["source_dataset"] == "scms"]
    if scms.empty:
        return primary

    extras: list[pd.DataFrame] = []
    per_supplier_cap = 30
    for _, grp in scms.groupby("supplier_id"):
        missing = grp[~grp["order_id"].astype(str).isin(selected_ids)].head(per_supplier_cap)
        if len(missing):
            extras.append(missing)

    if not extras:
        return primary

    combined = pd.concat([primary, *extras], ignore_index=True)
    return combined.drop_duplicates(subset=["order_id"], keep="first")


async def reset_real_graph(tenant_id: str) -> None:
    await run_write(
        """
        MATCH (n {tenant_id: $tenant_id})
        WHERE n.real_data = true
        DETACH DELETE n
        """,
        {"tenant_id": tenant_id},
    )


async def build_real_graph_from_normalized(
    tenant_id: str,
    normalized_dir: Path,
    *,
    limit: int | None = 5000,
) -> dict[str, int]:
    normalized_dir = Path(normalized_dir)
    await ensure_constraints()

    suppliers = _read_csv(normalized_dir, "suppliers")
    materials = _read_csv(normalized_dir, "materials")
    products = _read_csv(normalized_dir, "products")
    customers = _read_csv(normalized_dir, "customers")
    orders = _read_csv(normalized_dir, "orders")
    deliveries = _read_csv(normalized_dir, "deliveries")
    risks = _read_csv(normalized_dir, "risk_events")
    sm_edges = _read_csv(normalized_dir, "supplier_material_edges")
    mp_edges = _read_csv(normalized_dir, "material_product_edges")
    po_edges = _read_csv(normalized_dir, "product_order_edges")
    oc_edges = _read_csv(normalized_dir, "order_customer_edges")
    alt_edges = _read_csv(normalized_dir, "supplier_alternative_edges")

    merged = NormalizedDataset(
        dataset_name="runtime",
        tables={
            "suppliers": suppliers,
            "materials": materials,
            "products": products,
            "customers": customers,
            "orders": orders,
            "deliveries": deliveries,
            "risk_events": risks,
            "supplier_material_edges": sm_edges,
            "material_product_edges": mp_edges,
            "product_order_edges": po_edges,
            "order_customer_edges": oc_edges,
            "supplier_alternative_edges": alt_edges,
        },
    )
    merged = link_scms_suppliers_to_graph(merged)
    suppliers = merged.table("suppliers")
    materials = merged.table("materials")
    sm_edges = merged.table("supplier_material_edges")
    mp_edges = merged.table("material_product_edges")

    if limit:
        orders = _select_orders_for_graph(orders, limit)
        order_ids_selected = set(orders["order_id"].astype(str)) if len(orders) else set()
        if len(deliveries) and order_ids_selected:
            deliveries = deliveries[deliveries["order_id"].astype(str).isin(order_ids_selected)]
        if len(risks) and "supplier_id" in risks.columns:
            supplier_ids_selected = set(orders["supplier_id"].dropna().astype(str)) if len(orders) else set()
            risks = risks[
                risks["supplier_id"].astype(str).isin(supplier_ids_selected)
                if supplier_ids_selected
                else risks.head(limit)
            ]
        elif limit and len(risks):
            risks = risks.head(limit)

    # Only customers linked to selected orders
    order_ids_in_graph_prefetch = set(orders["order_id"].astype(str)) if len(orders) else set()
    if len(oc_edges) and order_ids_in_graph_prefetch:
        oc_edges = oc_edges[oc_edges["order_id"].astype(str).isin(order_ids_in_graph_prefetch)]
        linked_customers = set(oc_edges["customer_id"].astype(str))
        if len(customers) and linked_customers:
            customers = customers[customers["customer_id"].astype(str).isin(linked_customers)]
    if len(po_edges) and order_ids_in_graph_prefetch:
        po_edges = po_edges[po_edges["order_id"].astype(str).isin(order_ids_in_graph_prefetch)]

    supplier_code_by_ext: dict[str, str] = {}
    material_code_by_ext: dict[str, str] = {}
    product_code_by_ext: dict[str, str] = {}
    customer_code_by_ext: dict[str, str] = {}
    order_no_by_ext: dict[str, str] = {}

    for _, row in suppliers.iterrows():
        code = str(row["supplier_code"])[:64]
        supplier_code_by_ext[str(row["supplier_id"])] = code
        await upsert_supplier(
            tenant_id,
            {
                "id": str(row["supplier_id"]),
                "code": code,
                "name": str(row["supplier_name"]),
                "country": str(row.get("country") or ""),
                "tier": int(row.get("tier") or 1),
                "risk_score": float(row.get("risk_score") or 0),
                "status": str(row.get("status") or "active"),
                "metadata": {**_meta(row), "real_data": True},
            },
        )
        await run_write(
            "MATCH (n:Supplier {tenant_id: $tenant_id, code: $code}) SET n.real_data = true",
            {"tenant_id": tenant_id, "code": code},
        )

    for _, row in materials.iterrows():
        code = str(row["material_code"])[:64]
        material_code_by_ext[str(row["material_id"])] = code
        await upsert_material(
            tenant_id,
            {
                "id": str(row["material_id"]),
                "code": code,
                "name": str(row["material_name"]),
                "category": str(row.get("category") or ""),
                "is_critical": bool(row.get("is_critical")),
                "metadata": _meta(row),
            },
        )
        await run_write(
            "MATCH (n:Material {tenant_id: $tenant_id, code: $code}) SET n.real_data = true",
            {"tenant_id": tenant_id, "code": code},
        )

    for _, row in products.iterrows():
        code = str(row["product_code"])[:64]
        product_code_by_ext[str(row["product_id"])] = code
        await upsert_product(
            tenant_id,
            {
                "id": str(row["product_id"]),
                "code": code,
                "name": str(row["product_name"]),
                "category": str(row.get("category") or ""),
                "metadata": _meta(row),
            },
        )
        await run_write(
            "MATCH (n:Product {tenant_id: $tenant_id, code: $code}) SET n.real_data = true",
            {"tenant_id": tenant_id, "code": code},
        )

    for _, row in customers.iterrows():
        code = str(row["customer_id"])[:64]
        customer_code_by_ext[str(row["customer_id"])] = code
        await upsert_customer(
            tenant_id,
            {
                "id": code,
                "code": code,
                "name": str(row["customer_name"]),
                "region": str(row.get("region") or row.get("country") or ""),
                "tier": 1,
                "metadata": _meta(row),
            },
        )
        await run_write(
            "MATCH (n:Customer {tenant_id: $tenant_id, code: $code}) SET n.real_data = true",
            {"tenant_id": tenant_id, "code": code},
        )

    order_ids_in_graph = set()
    for _, row in orders.iterrows():
        order_no = str(row["order_no"])[:64]
        ext = str(row["order_id"])
        order_no_by_ext[ext] = order_no
        order_ids_in_graph.add(ext)
        await upsert_order(
            tenant_id,
            {
                "id": ext,
                "code": order_no,
                "order_no": order_no,
                "name": order_no,
                "status": str(row.get("order_status") or "open"),
                "expected_delivery_date": row.get("expected_delivery_date"),
                "metadata": _meta(row),
            },
        )
        await run_write(
            "MATCH (n:Order {tenant_id: $tenant_id, code: $code}) SET n.real_data = true",
            {"tenant_id": tenant_id, "code": order_no},
        )
        sup_ext = row.get("supplier_id")
        if pd.notna(sup_ext) and str(sup_ext) in supplier_code_by_ext:
            await merge_relationship(
                tenant_id,
                "Supplier",
                "code",
                supplier_code_by_ext[str(sup_ext)],
                "FULFILLS",
                "Order",
                "code",
                order_no,
                rel_props={"real_data": True, "source_dataset": row.get("source_dataset")},
            )

    delivery_by_order = (
        deliveries.set_index("order_id").to_dict(orient="index") if len(deliveries) else {}
    )
    for ext in order_ids_in_graph:
        drow = delivery_by_order.get(ext)
        if not drow:
            continue
        dev_id = str(drow.get("delivery_id") or f"DLV-{ext}")
        await upsert_delivery_event(
            tenant_id,
            {
                "id": dev_id,
                "order_no": order_no_by_ext.get(ext),
                "status": str(drow.get("delivery_status") or ""),
                "delay_days": int(pd.to_numeric(drow.get("delay_days"), errors="coerce") or 0),
                "delay_reason": drow.get("delay_reason"),
                "metadata": {"source_dataset": drow.get("source_dataset"), "real_data": True},
            },
        )
        sup_ext = drow.get("supplier_id")
        if pd.notna(sup_ext) and str(sup_ext) in supplier_code_by_ext:
            await merge_relationship(
                tenant_id,
                "Supplier",
                "code",
                supplier_code_by_ext[str(sup_ext)],
                "HAS_DELIVERY_EVENT",
                "DeliveryEvent",
                "id",
                dev_id,
            )
        order_no = order_no_by_ext.get(ext)
        if order_no:
            await merge_relationship(
                tenant_id,
                "Order",
                "code",
                order_no,
                "HAS_DELIVERY_EVENT",
                "DeliveryEvent",
                "id",
                dev_id,
            )

    for _, row in risks.iterrows():
        rid = str(row["risk_event_id"])
        await upsert_risk_event(
            tenant_id,
            {
                "id": rid,
                "event_type": str(row.get("event_type") or "unknown"),
                "severity": str(row.get("severity") or "medium"),
                "title": str(row.get("title") or "Risk"),
                "detected_at": row.get("detected_at"),
                "metadata": _meta(row, {"description": row.get("description")}),
            },
        )
        await run_write(
            "MATCH (n:RiskEvent {tenant_id: $tenant_id, id: $id}) SET n.real_data = true",
            {"tenant_id": tenant_id, "id": rid},
        )
        sup_ext = row.get("supplier_id")
        if pd.notna(sup_ext) and str(sup_ext) in supplier_code_by_ext:
            await merge_relationship(
                tenant_id,
                "Supplier",
                "code",
                supplier_code_by_ext[str(sup_ext)],
                "HAS_RISK_EVENT",
                "RiskEvent",
                "id",
                rid,
            )

    for _, row in sm_edges.iterrows():
        s_code = supplier_code_by_ext.get(str(row["supplier_id"]))
        m_code = material_code_by_ext.get(str(row["material_id"]))
        if s_code and m_code:
            await merge_relationship(
                tenant_id,
                "Supplier",
                "code",
                s_code,
                "SUPPLIES",
                "Material",
                "code",
                m_code,
                rel_props={"lead_time_days": row.get("lead_time_days"), "real_data": True},
            )

    for _, row in mp_edges.iterrows():
        m_code = material_code_by_ext.get(str(row["material_id"]))
        p_code = product_code_by_ext.get(str(row["product_id"]))
        if m_code and p_code:
            await merge_relationship(
                tenant_id,
                "Material",
                "code",
                m_code,
                "USED_IN",
                "Product",
                "code",
                p_code,
                rel_props={"real_data": True},
            )

    for _, row in po_edges.iterrows():
        p_code = product_code_by_ext.get(str(row["product_id"]))
        o_no = order_no_by_ext.get(str(row["order_id"]))
        if p_code and o_no:
            await merge_relationship(
                tenant_id,
                "Product",
                "code",
                p_code,
                "ORDERED_IN",
                "Order",
                "code",
                o_no,
            )

    for _, row in oc_edges.iterrows():
        o_no = order_no_by_ext.get(str(row["order_id"]))
        c_code = customer_code_by_ext.get(str(row["customer_id"]))
        if o_no and c_code:
            await merge_relationship(
                tenant_id,
                "Order",
                "code",
                o_no,
                "FOR_CUSTOMER",
                "Customer",
                "code",
                c_code,
            )

    for _, row in alt_edges.iterrows():
        s1 = supplier_code_by_ext.get(str(row["supplier_id"]))
        s2 = supplier_code_by_ext.get(str(row["alternative_supplier_id"]))
        if s1 and s2:
            await merge_relationship(
                tenant_id,
                "Supplier",
                "code",
                s1,
                "ALTERNATIVE_TO",
                "Supplier",
                "code",
                s2,
                rel_props={"similarity_score": row.get("similarity_score"), "real_data": True},
            )

    return await count_graph_stats(tenant_id)
