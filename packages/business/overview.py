"""Deterministic business exposure calculations; these are not model predictions."""

from decimal import Decimal

from packages.authz.constants import AUTHORIZATION_POLICY_VERSION
from packages.authz.rbac import UserContext
from packages.business.dataset import ManufacturingDataset, load_dataset

SEVERITY_RANK = {"medium": 1, "high": 2, "critical": 3}


def scenario_catalog(dataset: ManufacturingDataset | None = None) -> list[dict]:
    data = dataset or load_dataset()
    return [item.model_dump() for item in data.scenarios]


def business_overview(
    user_context: UserContext,
    scenario_id: str = "port-congestion",
    *,
    dataset: ManufacturingDataset | None = None,
) -> dict:
    if not user_context.is_member:
        raise PermissionError("enterprise membership required")
    data = dataset or load_dataset()
    scenario = next((s for s in data.scenarios if s.id == scenario_id), None)
    if scenario is None:
        raise KeyError(scenario_id)
    events = [e for e in data.risk_events if e.id in scenario.risk_event_ids]
    order_risks: dict[str, list] = {}
    for event in events:
        for order_id in event.affected_order_ids:
            order_risks.setdefault(order_id, []).append(event)
    suppliers = {s.id: s for s in data.suppliers}
    products = {p.id: p for p in data.products}
    orders = []
    for order in data.orders:
        if order.id not in order_risks or order.status in {"delivered", "cancelled"}:
            continue
        severity = max(
            (e.severity for e in order_risks[order.id]), key=SEVERITY_RANK.get
        )
        orders.append(
            {
                **order.model_dump(mode="json"),
                "severity": severity,
                "supplier_name": suppliers[order.supplier_id].name,
                "product_name": products[order.product_id].name,
                "risk_event_ids": [e.id for e in order_risks[order.id]],
            }
        )
    orders.sort(
        key=lambda o: (
            -SEVERITY_RANK[o["severity"]],
            -Decimal(o["amount_cny"]),
            o["id"],
        )
    )
    material_ids = {m for o in orders for m in products[o["product_id"]].material_ids}
    exposure = sum((Decimal(o["amount_cny"]) for o in orders), Decimal("0"))
    return {
        "tenant_id": str(user_context.tenant_id),
        "workspace_name": data.company_name,
        "policy_version": AUTHORIZATION_POLICY_VERSION,
        "provenance": {
            "source_type": data.source_type,
            "schema_version": data.schema_version,
            "dataset_version": data.dataset_version,
            "as_of": data.as_of.isoformat(),
            "label": "模拟业务数据 · 规则情景暴露",
            "notice": "此处风险关联为场景设定；库存传播见影响模拟，公开历史预测见预测验证。",
        },
        "scenario": scenario.model_dump(),
        "scenarios": scenario_catalog(data),
        "metrics": {
            "exposure_amount_cny": format(exposure, ".2f"),
            "at_risk_orders": len(orders),
            "pending_high_risk_orders": sum(
                o["severity"] in {"high", "critical"}
                and o["action_status"] != "resolved"
                for o in orders
            ),
            "active_risk_events": len(events),
            "critical_materials": sum(
                m.critical and m.id in material_ids for m in data.materials
            ),
        },
        "definitions": {
            "exposure_amount_cny": "当前场景关联的未交付、未取消唯一订单金额之和；多路径去重。不是预计损失。",
            "pending_high_risk_orders": "上述订单中风险为高/严重且处置尚未完成的唯一订单数量。",
            "active_risk_events": "当前场景内、截至演示时点已发现的风险事件数量。",
            "critical_materials": "受影响订单产品所依赖的关键物料种类数；不等同于已缺料种类数。",
        },
        "orders": orders,
        "risk_events": [e.model_dump(mode="json") for e in events],
        "network_summary": {
            "suppliers": len(data.suppliers),
            "sites": len(data.sites),
            "orders": len(data.orders),
            "shipments": len(data.shipments),
        },
        "capabilities": {
            "business_overview": "available",
            "map_tracking": "available",
            "inventory_simulation": "available",
            "trained_prediction": "manufacturing_not_validated",
            "public_prediction": "historical_validation_p4",
            "action_persistence": "available_workspace_p5",
        },
    }
