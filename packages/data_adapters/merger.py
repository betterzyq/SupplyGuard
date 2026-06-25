"""Merge normalized tables from multiple adapters."""

from __future__ import annotations

import pandas as pd

from packages.data_adapters.schema import NORMALIZED_COLUMNS, NORMALIZED_TABLE_NAMES, NormalizedDataset, empty_tables, empty_normalized


def _dedupe(df: pd.DataFrame, subset: list[str]) -> pd.DataFrame:
    if df.empty or not subset:
        return df
    present = [c for c in subset if c in df.columns]
    if not present:
        return df.drop_duplicates()
    return df.drop_duplicates(subset=present, keep="first")


def merge_normalized(datasets: list[NormalizedDataset]) -> NormalizedDataset:
    merged = empty_normalized("merged")

    for name in NORMALIZED_TABLE_NAMES:
        parts = [ds.table(name) for ds in datasets if len(ds.table(name)) > 0]
        if not parts:
            continue
        merged.tables[name] = pd.concat(parts, ignore_index=True)

    # Dedupe rules per table
    dedupe_keys = {
        "suppliers": ["supplier_id"],
        "facilities": ["facility_id"],
        "materials": ["material_id"],
        "products": ["product_id"],
        "customers": ["customer_id"],
        "orders": ["order_id"],
        "deliveries": ["delivery_id"],
        "risk_events": ["risk_event_id"],
        "supplier_material_edges": ["supplier_id", "material_id", "relationship_type"],
        "material_product_edges": ["material_id", "product_id"],
        "product_order_edges": ["product_id", "order_id"],
        "order_customer_edges": ["order_id", "customer_id"],
        "supplier_alternative_edges": ["supplier_id", "alternative_supplier_id", "material_id"],
        "country_risk_scores": ["country", "source"],
        "compliance_entities": ["entity_id"],
    }
    for name, keys in dedupe_keys.items():
        merged.tables[name] = _dedupe(merged.tables[name], keys)

    # Ensure column order
    for name in NORMALIZED_TABLE_NAMES:
        cols = NORMALIZED_COLUMNS[name]
        df = merged.tables[name]
        for col in cols:
            if col not in df.columns:
                df[col] = None
        merged.tables[name] = df[cols] if len(df) else df

    return NormalizedDataset(dataset_name="merged", tables=merged.tables)


def link_orders_to_graph(merged: NormalizedDataset) -> NormalizedDataset:
    """Fill product_order edges for SCMS orders using name/code heuristics if missing."""
    orders = merged.table("orders")
    products = merged.table("products")
    if orders.empty or products.empty:
        return merged

    po_edges = merged.table("product_order_edges")
    existing_orders = set(po_edges["order_id"].astype(str)) if len(po_edges) else set()

    new_edges = []
    product_ids = products["product_id"].tolist()
    for i, row in orders.iterrows():
        oid = row["order_id"]
        if str(oid) in existing_orders or row.get("source_dataset") != "scms":
            continue
        # Round-robin link SCMS orders to graph products for demo connectivity
        if product_ids:
            pid = product_ids[i % len(product_ids)]
            new_edges.append(
                {
                    "product_id": pid,
                    "order_id": oid,
                    "relationship_type": "ORDERED_IN",
                    "source_dataset": "merged_heuristic",
                }
            )
            orders.at[i, "product_id"] = pid

    if new_edges:
        merged.tables["product_order_edges"] = pd.concat(
            [po_edges, pd.DataFrame(new_edges)], ignore_index=True
        ).drop_duplicates(subset=["product_id", "order_id"], keep="first")
        merged.tables["orders"] = orders

    return merged


def link_scms_suppliers_to_graph(merged: NormalizedDataset) -> NormalizedDataset:
    """Wire SCMS suppliers into the material→product chain for GraphRAG paths."""
    orders = merged.table("orders")
    suppliers = merged.table("suppliers")
    products = merged.table("products")
    if orders.empty or suppliers.empty:
        return merged

    scms_orders = orders[orders.get("source_dataset") == "scms"] if "source_dataset" in orders.columns else pd.DataFrame()
    if scms_orders.empty:
        return merged

    po_edges = merged.table("product_order_edges")
    sm_edges = merged.table("supplier_material_edges")
    mp_edges = merged.table("material_product_edges")
    materials = merged.table("materials")

    supplier_code_by_id = {
        str(r["supplier_id"]): str(r["supplier_code"])
        for _, r in suppliers.iterrows()
        if pd.notna(r.get("supplier_id"))
    }
    existing_sm = set(
        zip(sm_edges["supplier_id"].astype(str), sm_edges["material_id"].astype(str))
        if len(sm_edges)
        else []
    )
    existing_mp = set(
        zip(mp_edges["material_id"].astype(str), mp_edges["product_id"].astype(str))
        if len(mp_edges)
        else []
    )
    material_rows: list[dict] = []
    sm_rows: list[dict] = []
    mp_rows: list[dict] = []

    po_by_order: dict[str, dict] = {}
    if len(po_edges):
        for _, po in po_edges.iterrows():
            po_by_order[str(po["order_id"])] = po.to_dict()

    for _, row in scms_orders.iterrows():
        sid = str(row.get("supplier_id") or "")
        if not sid or sid not in supplier_code_by_id:
            continue
        oid = str(row["order_id"])
        pid = str(row.get("product_id") or "")
        if not pid or pid == "nan":
            pid = str((po_by_order.get(oid) or {}).get("product_id") or "")
        if not pid or pid == "nan":
            continue

        scode = supplier_code_by_id[sid]
        mat_id = f"SCMS-MAT-{scode}"[:64]
        known_materials = set(materials["material_id"].astype(str)) if len(materials) else set()
        if mat_id not in known_materials and mat_id not in {m["material_id"] for m in material_rows}:
            material_rows.append(
                {
                    "material_id": mat_id,
                    "material_code": mat_id,
                    "material_name": f"SCMS supply bundle ({scode})",
                    "category": "scms_synthetic",
                    "is_critical": False,
                    "source_dataset": "merged_heuristic",
                }
            )

        sm_key = (sid, mat_id)
        if sm_key not in existing_sm:
            sm_rows.append(
                {
                    "supplier_id": sid,
                    "material_id": mat_id,
                    "relationship_type": "SUPPLIES",
                    "lead_time_days": None,
                    "source_dataset": "merged_heuristic",
                }
            )
            existing_sm.add(sm_key)

        mp_key = (mat_id, pid)
        if mp_key not in existing_mp:
            mp_rows.append(
                {
                    "material_id": mat_id,
                    "product_id": pid,
                    "relationship_type": "USED_IN",
                    "source_dataset": "merged_heuristic",
                }
            )
            existing_mp.add(mp_key)

    if material_rows:
        merged.tables["materials"] = pd.concat([materials, pd.DataFrame(material_rows)], ignore_index=True).drop_duplicates(
            subset=["material_id"], keep="first"
        )
    if sm_rows:
        merged.tables["supplier_material_edges"] = pd.concat(
            [sm_edges, pd.DataFrame(sm_rows)], ignore_index=True
        ).drop_duplicates(subset=["supplier_id", "material_id"], keep="first")
    if mp_rows:
        merged.tables["material_product_edges"] = pd.concat(
            [mp_edges, pd.DataFrame(mp_rows)], ignore_index=True
        ).drop_duplicates(subset=["material_id", "product_id"], keep="first")

    return merged
