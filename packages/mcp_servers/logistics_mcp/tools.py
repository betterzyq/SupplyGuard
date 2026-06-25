"""Logistics MCP stub tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.authz.tool_policy import enforce_supplier_scope
from packages.common.db.models.order import Order
from packages.common.db.models.supplier import Supplier


def _load_graph_seed() -> dict:
    path = Path(__file__).resolve().parents[3] / "data" / "seed" / "graph_seed.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


async def query_delivery_status(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    order_no = tool_input.get("order_no")
    supplier_code = tool_input.get("supplier_code")
    ok, reason, scoped = await enforce_supplier_scope(session, user_context, supplier_code)
    if not ok:
        return {"error": reason, "status": "denied"}
    if order_no:
        order = (
            await session.execute(
                select(Order).where(
                    Order.tenant_id == user_context.tenant_id,
                    Order.order_no == str(order_no),
                )
            )
        ).scalar_one_or_none()
        if order:
            return {
                "order_no": order.order_no,
                "status": order.status,
                "product_name": order.product_name,
                "customer_name": order.customer_name,
            }
    if scoped or supplier_code:
        code = scoped or supplier_code
        supplier = (
            await session.execute(
                select(Supplier).where(
                    Supplier.tenant_id == user_context.tenant_id,
                    Supplier.code == str(code).upper(),
                )
            )
        ).scalar_one_or_none()
        if supplier:
            orders = (
                await session.execute(
                    select(Order)
                    .where(Order.tenant_id == user_context.tenant_id, Order.supplier_id == supplier.id)
                    .limit(5)
                )
            ).scalars().all()
            return {
                "supplier_code": supplier.code,
                "orders": [{"order_no": o.order_no, "status": o.status} for o in orders],
            }
    return {"error": "order or supplier not found", "status": "not_found"}


async def query_delay_events(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    seed = _load_graph_seed()
    events = seed.get("delivery_events") or []
    supplier_code = tool_input.get("supplier_code")
    ok, reason, scoped = await enforce_supplier_scope(session, user_context, supplier_code)
    if not ok:
        return {"error": reason, "status": "denied"}
    if scoped or supplier_code:
        code = (scoped or supplier_code or "").upper()
        events = [e for e in events if e.get("supplier_code") == code]
    delayed = [e for e in events if int(e.get("delay_days") or 0) > 0]
    return {"delay_events": delayed, "count": len(delayed)}


async def query_route_info(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    origin = tool_input.get("origin") or "Shanghai Port"
    destination = tool_input.get("destination") or "Shenzhen Warehouse"
    return {
        "origin": origin,
        "destination": destination,
        "route": f"{origin} → East China Hub → {destination}",
        "estimated_days": 5,
        "status": "stub",
        "note": "Mock route info for Stage C",
    }
