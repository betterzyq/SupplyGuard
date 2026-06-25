"""Load normalized CSV tables into PostgreSQL (additive; preserves seed data)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.order import Order
from packages.common.db.models.risk_event import RiskEvent
from packages.common.db.models.supplier import Supplier
from packages.common.db.models.tenant import Tenant

TENANT_CODE = "demo-mfg"
SYNTHETIC_DATACO_SUPPLIER_CODE = "REAL-DATACO-CHANNEL"
BATCH_SIZE = 1000


from packages.data_adapters.utils import fix_mojibake, pg_uuid


def _parse_date(val) -> datetime | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    ts = pd.to_datetime(val, errors="coerce")
    if pd.isna(ts):
        return None
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


def read_table(normalized_dir: Path, name: str) -> pd.DataFrame:
    path = normalized_dir / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


class RealDataLoadReport:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.skipped: dict[str, int] = {}
        self.dry_run: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"counts": self.counts, "skipped": self.skipped, "dry_run": self.dry_run}


def _real_order_filter(tenant_id: uuid.UUID):
    """Orders loaded from external datasets (no metadata column on Order)."""
    return (
        Order.tenant_id == tenant_id,
        or_(
            Order.order_no.like("DC-ORD-%"),
            Order.order_no.like("DC-%"),
            Order.order_no.like("SCMS-%"),
        ),
    )


async def _delete_by_ids(
    session: AsyncSession,
    model,
    tenant_id: uuid.UUID,
    ids: list[uuid.UUID],
) -> int:
    total = 0
    for i in range(0, len(ids), BATCH_SIZE):
        chunk = ids[i : i + BATCH_SIZE]
        result = await session.execute(
            delete(model).where(model.tenant_id == tenant_id, model.id.in_(chunk))
        )
        total += result.rowcount or 0
    return total


async def reset_real_data(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    normalized_dir: Path | None = None,
    limit: int | None = None,
) -> dict[str, int]:
    """Remove previously loaded real-data rows; keep seed demo records."""
    deleted: dict[str, int] = {}

    order_ids: list[uuid.UUID] = []
    risk_ids: list[uuid.UUID] = []
    if normalized_dir and limit:
        orders_df = read_table(normalized_dir, "orders").head(limit)
        risks_df = read_table(normalized_dir, "risk_events").head(limit)
        order_ids = [
            pg_uuid(str(x))
            for x in orders_df.get("order_id", pd.Series(dtype=str)).dropna().unique()
        ]
        risk_ids = [
            pg_uuid(str(x))
            for x in risks_df.get("risk_event_id", pd.Series(dtype=str)).dropna().unique()
        ]

    # FK order: risk_events -> suppliers, orders -> suppliers
    if risk_ids:
        deleted["risk_events"] = await _delete_by_ids(session, RiskEvent, tenant_id, risk_ids)
    else:
        risk_result = await session.execute(
            delete(RiskEvent).where(
                RiskEvent.tenant_id == tenant_id,
                RiskEvent.metadata_["real_data"].as_boolean() == True,  # noqa: E712
            )
        )
        deleted["risk_events"] = risk_result.rowcount or 0

    if order_ids:
        deleted["orders"] = await _delete_by_ids(session, Order, tenant_id, order_ids)
    else:
        order_result = await session.execute(delete(Order).where(*_real_order_filter(tenant_id)))
        deleted["orders"] = order_result.rowcount or 0

    # Partial reset (--limit) may leave orders referencing suppliers; skip supplier delete.
    if not limit:
        supplier_result = await session.execute(
            delete(Supplier).where(
                Supplier.tenant_id == tenant_id,
                Supplier.metadata_["real_data"].as_boolean() == True,  # noqa: E712
            )
        )
        deleted["suppliers"] = supplier_result.rowcount or 0

    await session.flush()
    return deleted


async def ensure_synthetic_suppliers(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Suppliers required for nullable FK fields in normalized data."""
    codes = {
        SYNTHETIC_DATACO_SUPPLIER_CODE: "DataCo Logistics Channel (synthetic aggregator)",
    }
    mapping: dict[str, uuid.UUID] = {}
    for code, name in codes.items():
        existing = (
            await session.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.code == code)
            )
        ).scalar_one_or_none()
        if existing:
            mapping[code] = existing.id
            continue
        supplier = Supplier(
            id=pg_uuid(code),
            tenant_id=tenant_id,
            code=code,
            name=name,
            country="GLOBAL",
            tier=3,
            risk_score=Decimal("0"),
            status="active",
            metadata_={"real_data": True, "synthetic": True, "source_dataset": "system"},
        )
        session.add(supplier)
        mapping[code] = supplier.id
    await session.flush()
    return mapping


async def load_real_data_to_postgres(
    session: AsyncSession,
    normalized_dir: Path,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    reset: bool = False,
) -> RealDataLoadReport:
    report = RealDataLoadReport()
    report.dry_run = dry_run
    normalized_dir = Path(normalized_dir)

    tenant = (
        await session.execute(select(Tenant).where(Tenant.code == TENANT_CODE))
    ).scalar_one_or_none()
    if tenant is None:
        raise RuntimeError(f"Tenant {TENANT_CODE} not found. Run make seed first.")

    if reset and not dry_run:
        report.counts["reset"] = sum(
            (await reset_real_data(session, tenant.id, normalized_dir, limit)).values()
        )

    synthetic = await ensure_synthetic_suppliers(session, tenant.id)
    dataco_supplier_id = synthetic[SYNTHETIC_DATACO_SUPPLIER_CODE]

    suppliers_df = read_table(normalized_dir, "suppliers")
    products_df = read_table(normalized_dir, "products")
    customers_df = read_table(normalized_dir, "customers")
    orders_df = read_table(normalized_dir, "orders")
    risk_df = read_table(normalized_dir, "risk_events")

    if limit:
        suppliers_df = suppliers_df.head(min(limit, len(suppliers_df)))
        orders_df = orders_df.head(limit)
        risk_df = risk_df.head(limit)

    product_names = (
        products_df.set_index("product_id")["product_name"].to_dict() if len(products_df) else {}
    )
    customer_names = (
        customers_df.set_index("customer_id")["customer_name"].to_dict() if len(customers_df) else {}
    )

    existing_supplier_codes = {
        row[0]
        for row in (
            await session.execute(select(Supplier.code).where(Supplier.tenant_id == tenant.id))
        ).all()
    }
    existing_order_nos = {
        row[0]
        for row in (
            await session.execute(select(Order.order_no).where(Order.tenant_id == tenant.id))
        ).all()
    }
    existing_order_ids = {
        row[0]
        for row in (await session.execute(select(Order.id).where(Order.tenant_id == tenant.id))).all()
    }
    existing_risk_ids = {
        row[0]
        for row in (
            await session.execute(select(RiskEvent.id).where(RiskEvent.tenant_id == tenant.id))
        ).all()
    }

    existing_supplier_ids = {
        row[0]
        for row in (
            await session.execute(select(Supplier.id).where(Supplier.tenant_id == tenant.id))
        ).all()
    }

    supplier_uuid_by_external: dict[str, uuid.UUID] = {}
    for sup in (
        await session.execute(select(Supplier).where(Supplier.tenant_id == tenant.id))
    ).scalars():
        ext = (sup.metadata_ or {}).get("external_id")
        if ext:
            supplier_uuid_by_external[str(ext)] = sup.id

    # --- Suppliers ---
    loaded_suppliers = 0
    skipped_suppliers = 0
    for _, row in suppliers_df.iterrows():
        code = str(row["supplier_code"])
        ext_id = str(row["supplier_id"])
        sid = pg_uuid(ext_id)
        if code in existing_supplier_codes or sid in existing_supplier_ids:
            skipped_suppliers += 1
            existing = (
                await session.execute(
                    select(Supplier).where(
                        Supplier.tenant_id == tenant.id,
                        or_(Supplier.code == code, Supplier.id == sid),
                    )
                )
            ).scalar_one_or_none()
            if existing:
                supplier_uuid_by_external[ext_id] = existing.id
            continue
        supplier_uuid_by_external[ext_id] = sid
        if dry_run:
            loaded_suppliers += 1
            continue
        session.add(
            Supplier(
                id=sid,
                tenant_id=tenant.id,
                code=code[:64],
                name=fix_mojibake(str(row["supplier_name"])) or code,
                country=fix_mojibake(str(row["country"])) or "UNKNOWN",
                tier=int(row["tier"]) if pd.notna(row.get("tier")) else 1,
                risk_score=Decimal(str(row.get("risk_score") or 0)),
                status=str(row.get("status") or "active"),
                metadata_={
                    "real_data": True,
                    "external_id": ext_id,
                    "source_dataset": row.get("source_dataset"),
                },
            )
        )
        loaded_suppliers += 1
        existing_supplier_codes.add(code)
        existing_supplier_ids.add(sid)
        if loaded_suppliers % BATCH_SIZE == 0:
            await session.flush()

    if not dry_run:
        await session.flush()
    report.counts["suppliers"] = loaded_suppliers
    report.skipped["suppliers"] = skipped_suppliers

    # --- Orders ---
    loaded_orders = 0
    skipped_orders = 0
    for _, row in orders_df.iterrows():
        ext_id = str(row["order_id"])
        oid = pg_uuid(ext_id)
        if oid in existing_order_ids:
            skipped_orders += 1
            continue

        order_no = str(row["order_no"])[:64]
        if order_no in existing_order_nos:
            skipped_orders += 1
            continue

        ext_supplier = row.get("supplier_id")
        if pd.notna(ext_supplier) and str(ext_supplier) in supplier_uuid_by_external:
            supplier_id = supplier_uuid_by_external[str(ext_supplier)]
        else:
            supplier_id = dataco_supplier_id

        pid = row.get("product_id")
        cid = row.get("customer_id")
        product_name = product_names.get(pid, "Unknown Product") if pd.notna(pid) else "Unknown Product"
        customer_name = customer_names.get(cid, "Unknown Customer") if pd.notna(cid) else "Unknown Customer"

        qty = int(pd.to_numeric(row.get("quantity"), errors="coerce") or 1)
        expected = _parse_date(row.get("expected_delivery_date"))
        expected_date = expected.date() if expected else None

        if dry_run:
            loaded_orders += 1
            continue

        session.add(
            Order(
                id=oid,
                tenant_id=tenant.id,
                order_no=order_no,
                supplier_id=supplier_id,
                product_name=str(product_name)[:255],
                customer_name=str(customer_name)[:255],
                quantity=max(qty, 1),
                status=str(row.get("order_status") or "open")[:32],
                expected_delivery_date=expected_date,
            )
        )
        existing_order_nos.add(order_no)
        existing_order_ids.add(oid)
        loaded_orders += 1
        if loaded_orders % BATCH_SIZE == 0:
            await session.flush()

    if not dry_run:
        await session.flush()
    report.counts["orders"] = loaded_orders
    report.skipped["orders"] = skipped_orders

    # --- Risk events ---
    loaded_risks = 0
    skipped_risks = 0
    for _, row in risk_df.iterrows():
        ext_id = str(row["risk_event_id"])
        rid = pg_uuid(ext_id)
        if rid in existing_risk_ids:
            skipped_risks += 1
            continue

        ext_supplier = row.get("supplier_id")
        if pd.notna(ext_supplier) and str(ext_supplier) in supplier_uuid_by_external:
            supplier_id = supplier_uuid_by_external[str(ext_supplier)]
        else:
            supplier_id = dataco_supplier_id

        detected = _parse_date(row.get("detected_at")) or datetime.now(UTC)

        if dry_run:
            loaded_risks += 1
            continue

        session.add(
            RiskEvent(
                id=rid,
                tenant_id=tenant.id,
                supplier_id=supplier_id,
                event_type=str(row.get("event_type") or "unknown")[:64],
                severity=str(row.get("severity") or "medium")[:32],
                title=str(row.get("title") or "Risk event")[:512],
                description=str(row.get("description") or "")[:4000],
                source=str(row.get("source") or row.get("source_dataset") or "real_data")[:255],
                detected_at=detected,
                metadata_={
                    "real_data": True,
                    "external_id": ext_id,
                    "source_dataset": row.get("source_dataset"),
                    "country": row.get("country"),
                },
            )
        )
        existing_risk_ids.add(rid)
        loaded_risks += 1
        if loaded_risks % BATCH_SIZE == 0:
            await session.flush()

    if not dry_run:
        await session.flush()
    report.counts["risk_events"] = loaded_risks
    report.skipped["risk_events"] = skipped_risks

    return report
