"""Geographic and shipment replay; simulated coordinates, never live tracking."""

from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from math import asin, cos, degrees, radians, sin
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.authz.rbac import UserContext
from packages.business.dataset import load_dataset
from packages.business.overview import SEVERITY_RANK

REPLAY_PATH = Path(__file__).resolve().parents[2] / "data/demo/network-v1.json"


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    at: datetime


class Milestone(BaseModel):
    name: str
    planned_at: datetime
    observed_at: datetime | None = None


class EtaUpdate(BaseModel):
    observed_at: datetime
    eta: datetime
    reason: str


class Journey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shipment_id: str
    route: list[list[float]] = Field(min_length=2)
    trace: list[Point] = Field(min_length=2)
    milestones: list[Milestone] = Field(min_length=2)
    eta_updates: list[EtaUpdate] = Field(default_factory=list)
    carrier: str


class ReplayDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    coordinate_system: Literal["WGS84"]
    start_at: datetime
    end_at: datetime
    journeys: list[Journey]
    risk_radius_km: dict[str, float]

    @model_validator(mode="after")
    def integrity(self):
        base = load_dataset()
        if (
            self.start_at.utcoffset() is None
            or self.end_at.utcoffset() is None
            or self.start_at >= self.end_at
            or self.end_at != base.as_of
        ):
            raise ValueError("invalid replay time bounds")
        source_shipments = {s.id: s for s in base.shipments}
        sites = {s.id: s for s in base.sites}
        if {j.shipment_id for j in self.journeys} != set(source_shipments) or len(
            self.journeys
        ) != len(source_shipments):
            raise ValueError("journeys must match shipments exactly")
        for event in base.risk_events:
            if (
                event.id not in self.risk_radius_km
                or not 0 < self.risk_radius_km[event.id] <= 500
            ):
                raise ValueError("invalid demonstration risk radius")
        for j in self.journeys:
            ship = source_shipments[j.shipment_id]
            for coordinate in j.route:
                if (
                    len(coordinate) != 2
                    or not -180 <= coordinate[0] <= 180
                    or not -90 <= coordinate[1] <= 90
                ):
                    raise ValueError("invalid route coordinate")
            for edge, site_id in [
                (j.route[0], ship.origin_site_id),
                (j.route[-1], ship.destination_site_id),
            ]:
                site = sites[site_id]
                if (
                    abs(edge[0] - site.longitude) > 1e-6
                    or abs(edge[1] - site.latitude) > 1e-6
                ):
                    raise ValueError("route endpoints must match sites")
            timestamps = [p.at for p in j.trace]
            if (
                any(t.utcoffset() is None for t in timestamps)
                or any(a >= b for a, b in zip(timestamps, timestamps[1:]))
                or timestamps[-1] > self.end_at
            ):
                raise ValueError(
                    "trajectory must be ordered, zoned and no later than snapshot"
                )
            for m in j.milestones:
                if m.planned_at.utcoffset() is None or (
                    m.observed_at is not None
                    and (
                        m.observed_at.utcoffset() is None or m.observed_at > self.end_at
                    )
                ):
                    raise ValueError("invalid milestone time")
            for update in j.eta_updates:
                if (
                    update.observed_at.utcoffset() is None
                    or update.eta.utcoffset() is None
                    or update.observed_at > self.end_at
                ):
                    raise ValueError("invalid ETA update")
        return self


@lru_cache(maxsize=1)
def load_replay():
    return ReplayDataset.model_validate_json(REPLAY_PATH.read_text())


def parse_time(value: datetime | None, replay: ReplayDataset) -> datetime:
    at = value or replay.end_at
    if at.utcoffset() is None or not replay.start_at <= at <= replay.end_at:
        raise ValueError("回放时间必须包含时区且位于演示范围内")
    return at


def clip_trace(points: list[Point], at: datetime) -> list[dict]:
    result = [p.model_dump(mode="json") for p in points if p.at <= at]
    for left, right in zip(points, points[1:]):
        if left.at < at < right.at:
            fraction = (at - left.at).total_seconds() / (
                right.at - left.at
            ).total_seconds()
            result.append(
                {
                    "longitude": left.longitude
                    + (right.longitude - left.longitude) * fraction,
                    "latitude": left.latitude
                    + (right.latitude - left.latitude) * fraction,
                    "at": at.isoformat(),
                }
            )
            break
    return result


def circle(longitude: float, latitude: float, radius_km: float):
    lon, lat, distance = radians(longitude), radians(latitude), radius_km / 6371
    ring = []
    from math import atan2

    for step in range(65):
        bearing = step / 64 * 2 * 3.141592653589793
        y = asin(sin(lat) * cos(distance) + cos(lat) * sin(distance) * cos(bearing))
        x = lon + atan2(
            sin(bearing) * sin(distance) * cos(lat), cos(distance) - sin(lat) * sin(y)
        )
        ring.append([degrees(x), degrees(y)])
    ring[-1] = ring[0][:]
    return ring


def dependency_paths(order, base):
    product = next(p for p in base.products if p.id == order.product_id)
    material_lookup = {m.id: m for m in base.materials}
    supplier_lookup = {s.id: s for s in base.suppliers}
    paths = []
    for material_id in product.material_ids:
        material = material_lookup[material_id]
        for supplier_id in material.supplier_ids:
            supplier = supplier_lookup[supplier_id]
            paths.append(
                {
                    "nodes": [
                        {
                            "id": supplier.id,
                            "name": supplier.name,
                            "type": "Supplier",
                            "site_id": supplier.site_id,
                        },
                        {"id": material.id, "name": material.name, "type": "Material"},
                        {"id": product.id, "name": product.name, "type": "Product"},
                        {"id": order.id, "name": order.id, "type": "Order"},
                        {
                            "id": order.customer,
                            "name": order.customer,
                            "type": "Customer",
                        },
                    ],
                    "relationships": ["供应", "用于生产", "关联订单", "交付客户"],
                }
            )
    return paths


def network_snapshot(
    user: UserContext,
    scenario_id="port-congestion",
    at_time: datetime | None = None,
    supplier_id: str | None = None,
    mode: str | None = None,
    q="",
    risk_only=False,
) -> dict:
    if not user.is_member:
        raise PermissionError("enterprise membership required")
    base, replay = load_dataset(), load_replay()
    scenario = next((s for s in base.scenarios if s.id == scenario_id), None)
    if scenario is None:
        raise KeyError("Unknown scenario")
    if supplier_id and supplier_id not in {s.id for s in base.suppliers}:
        raise KeyError("Unknown supplier")
    at = parse_time(at_time, replay)
    events = [
        e
        for e in base.risk_events
        if e.id in scenario.risk_event_ids and e.detected_at <= at
    ]
    suppliers = {s.id: s for s in base.suppliers}
    products = {p.id: p for p in base.products}
    orders = []
    for order in base.orders:
        if order.status in {"delivered", "cancelled"}:
            continue
        ships = [s for s in base.shipments if order.id in s.order_ids]
        risks = [e for e in events if order.id in e.affected_order_ids]
        search = " ".join(
            [
                order.id,
                order.customer,
                suppliers[order.supplier_id].name,
                products[order.product_id].name,
                *[s.id for s in ships],
            ]
        ).lower()
        if (
            (supplier_id and order.supplier_id != supplier_id)
            or (mode and not any(s.mode == mode for s in ships))
            or (q.lower().strip() not in search)
            or (risk_only and not risks)
        ):
            continue
        orders.append(
            {
                **order.model_dump(mode="json"),
                "supplier_name": suppliers[order.supplier_id].name,
                "product_name": products[order.product_id].name,
                "severity": max(
                    (e.severity for e in risks), key=SEVERITY_RANK.get, default=None
                ),
                "risk_event_ids": [e.id for e in risks],
                "shipment_ids": [s.id for s in ships],
                "dependency_paths": dependency_paths(order, base),
            }
        )
    order_ids = {o["id"] for o in orders}
    visible_events = [e for e in events if order_ids.intersection(e.affected_order_ids)]
    journeys = {j.shipment_id: j for j in replay.journeys}
    shipments = []
    for ship in base.shipments:
        if not order_ids.intersection(ship.order_ids):
            continue
        journey = journeys[ship.id]
        trace = clip_trace(journey.trace, at)
        updates = [u for u in journey.eta_updates if u.observed_at <= at]
        latest = max(updates, key=lambda u: u.observed_at) if updates else None
        eta = latest.eta if latest else ship.eta
        shipments.append(
            {
                **ship.model_dump(mode="json"),
                "order_ids": [o for o in ship.order_ids if o in order_ids],
                "planned_eta": ship.eta.isoformat(),
                "eta": eta.isoformat(),
                "eta_source": "模拟计划更新，非训练模型预测",
                "eta_reason": latest.reason if latest else "演示运输计划",
                "eta_updates": [u.model_dump(mode="json") for u in updates],
                "delay_hours": max(
                    0, round((eta - ship.eta).total_seconds() / 3600, 1)
                ),
                "route": journey.route,
                "trace": trace,
                "position": trace[-1] if trace else None,
                "position_source": "模拟轨迹插值，非实时定位",
                "carrier": journey.carrier,
                "milestones": [
                    {
                        "name": m.name,
                        "planned_at": m.planned_at.isoformat(),
                        "observed_at": (
                            m.observed_at.isoformat()
                            if m.observed_at and m.observed_at <= at
                            else None
                        ),
                    }
                    for m in journey.milestones
                ],
            }
        )
    risk_site_ids = {site_id for e in visible_events for site_id in e.site_ids}
    site_ids = (
        risk_site_ids
        | {o["destination_site_id"] for o in orders}
        | {suppliers[o["supplier_id"]].site_id for o in orders}
    )
    for order in orders:
        for path in order["dependency_paths"]:
            site_ids.add(path["nodes"][0]["site_id"])
    for ship in shipments:
        site_ids.update([ship["origin_site_id"], ship["destination_site_id"]])
    sites = [
        {
            **s.model_dump(),
            "risk_event_ids": [e.id for e in visible_events if s.id in e.site_ids],
        }
        for s in base.sites
        if s.id in site_ids
    ]
    polygons = []
    lookup = {s.id: s for s in base.sites}
    for e in visible_events:
        for site_id in e.site_ids:
            site = lookup[site_id]
            polygons.append(
                {
                    "event_id": e.id,
                    "site_id": site_id,
                    "severity": e.severity,
                    "polygon": circle(
                        site.longitude, site.latitude, replay.risk_radius_km[e.id]
                    ),
                }
            )
    exposed = [o for o in orders if o["risk_event_ids"]]
    return {
        "tenant_id": str(user.tenant_id),
        "source_type": "synthetic",
        "dataset_version": replay.version,
        "coordinate_system": replay.coordinate_system,
        "as_of": at.isoformat(),
        "timeline": {
            "start_at": replay.start_at.isoformat(),
            "end_at": replay.end_at.isoformat(),
        },
        "scenario": scenario.model_dump(),
        "scenarios": [s.model_dump() for s in base.scenarios],
        "suppliers": [s.model_dump() for s in base.suppliers],
        "sites": sites,
        "orders": orders,
        "shipments": shipments,
        "risk_events": [e.model_dump(mode="json") for e in visible_events],
        "risk_areas": polygons,
        "metrics": {
            "exposure_amount_cny": format(
                sum((Decimal(o["amount_cny"]) for o in exposed), Decimal("0")), ".2f"
            ),
            "at_risk_orders": len(exposed),
            "visible_orders": len(orders),
            "visible_sites": len(sites),
            "visible_shipments": len(shipments),
            "active_risk_events": len(visible_events),
        },
        "filters": {
            "supplier_id": supplier_id,
            "mode": mode,
            "q": q,
            "risk_only": risk_only,
        },
        "notice": "WGS84 · 模拟路线与轨迹；风险圈为演示覆盖区，关联不是已验证传播。P3 才计算库存约束影响。",
    }
