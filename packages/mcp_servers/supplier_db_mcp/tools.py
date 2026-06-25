"""Supplier DB MCP stub tools."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.rbac import UserContext
from packages.authz.tool_policy import enforce_supplier_scope
from packages.common.db.models.document import Document
from packages.common.db.models.order import Order
from packages.common.db.models.risk_event import RiskEvent
from packages.common.db.models.supplier import Supplier


def _normalize_code(value: str | None) -> str | None:
    if not value:
        return None
    upper = str(value).upper().strip()
    if upper.startswith("S") and not upper.startswith("SUP-"):
        digits = upper.lstrip("S")
        if digits.isdigit():
            return f"SUP-{digits.zfill(3)}"
    return upper


async def _resolve_supplier(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    supplier_code: str | None,
    supplier_id: str | None,
) -> Supplier | None:
    code = _normalize_code(supplier_code)
    if code:
        return (
            await session.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.code == code)
            )
        ).scalar_one_or_none()
    if supplier_id:
        try:
            sid = uuid.UUID(str(supplier_id))
        except ValueError:
            return None
        return (
            await session.execute(
                select(Supplier).where(Supplier.tenant_id == tenant_id, Supplier.id == sid)
            )
        ).scalar_one_or_none()
    return None


async def query_supplier_profile(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    code = _normalize_code(tool_input.get("supplier_code") or tool_input.get("supplier_id"))
    ok, reason, scoped = await enforce_supplier_scope(session, user_context, code)
    if not ok:
        return {"error": reason, "status": "denied"}
    supplier = await _resolve_supplier(session, user_context.tenant_id, scoped or code, tool_input.get("supplier_id"))
    if supplier is None:
        return {"error": "supplier not found", "status": "not_found"}
    return {
        "supplier_code": supplier.code,
        "name": supplier.name,
        "country": supplier.country,
        "tier": supplier.tier,
        "risk_score": float(supplier.risk_score),
        "status": supplier.status,
    }


async def query_supplier_risk_events(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    code = _normalize_code(tool_input.get("supplier_code") or tool_input.get("supplier_id"))
    ok, reason, scoped = await enforce_supplier_scope(session, user_context, code)
    if not ok:
        return {"error": reason, "status": "denied"}
    supplier = await _resolve_supplier(session, user_context.tenant_id, scoped or code, tool_input.get("supplier_id"))
    if supplier is None:
        return {"error": "supplier not found", "events": []}
    events = (
        await session.execute(
            select(RiskEvent)
            .where(RiskEvent.tenant_id == user_context.tenant_id, RiskEvent.supplier_id == supplier.id)
            .order_by(RiskEvent.detected_at.desc())
            .limit(int(tool_input.get("limit") or 10))
        )
    ).scalars().all()
    return {
        "supplier_code": supplier.code,
        "events": [
            {
                "title": e.title,
                "event_type": e.event_type,
                "severity": e.severity,
                "detected_at": e.detected_at.isoformat(),
            }
            for e in events
        ],
    }


async def query_supplier_delivery_history(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    code = _normalize_code(tool_input.get("supplier_code") or tool_input.get("supplier_id"))
    ok, reason, scoped = await enforce_supplier_scope(session, user_context, code)
    if not ok:
        return {"error": reason, "status": "denied"}
    supplier = await _resolve_supplier(session, user_context.tenant_id, scoped or code, tool_input.get("supplier_id"))
    if supplier is None:
        return {"error": "supplier not found", "orders": []}
    orders = (
        await session.execute(
            select(Order)
            .where(Order.tenant_id == user_context.tenant_id, Order.supplier_id == supplier.id)
            .order_by(Order.created_at.desc())
            .limit(int(tool_input.get("limit") or 10))
        )
    ).scalars().all()
    return {
        "supplier_code": supplier.code,
        "orders": [
            {
                "order_no": o.order_no,
                "product_name": o.product_name,
                "customer_name": o.customer_name,
                "status": o.status,
                "expected_delivery_date": o.expected_delivery_date.isoformat() if o.expected_delivery_date else None,
            }
            for o in orders
        ],
    }


async def query_supplier_contract_summary(
    session: AsyncSession,
    user_context: UserContext,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    code = _normalize_code(tool_input.get("supplier_code") or tool_input.get("supplier_id"))
    supplier = await _resolve_supplier(session, user_context.tenant_id, code, tool_input.get("supplier_id"))
    if supplier is None:
        return {"error": "supplier not found"}
    docs = (
        await session.execute(
            select(Document).where(
                Document.tenant_id == user_context.tenant_id,
                Document.supplier_id == supplier.id,
                Document.doc_type == "contract",
            )
        )
    ).scalars().all()
    if not docs:
        docs = (
            await session.execute(
                select(Document).where(
                    Document.tenant_id == user_context.tenant_id,
                    Document.title.ilike("%contract%"),
                )
            )
        ).scalars().all()
    summaries = [
        {
            "title": doc.title,
            "doc_type": doc.doc_type,
            "security_level": doc.security_level,
            "summary": f"Contract document {doc.title} (stub summary — use Secure RAG for full text).",
        }
        for doc in docs[:3]
    ]
    return {"supplier_code": supplier.code, "contracts": summaries}
