"""Bounded contracts for deterministic, synthetic daily production planning."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Qty = Annotated[Decimal, Field(ge=0, le=1000000, decimal_places=4, allow_inf_nan=False)]
Cost = Annotated[
    Decimal, Field(ge=0, le=100000000, decimal_places=2, allow_inf_nan=False)
]
Identifier = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class Inventory(StrictModel):
    id: Identifier
    name: str = Field(max_length=100)
    initial_stock: Qty
    unit: str = "件"


class Component(StrictModel):
    component_id: Identifier
    quantity: Annotated[
        Decimal, Field(gt=0, le=100, decimal_places=4, allow_inf_nan=False)
    ]


class ProductionOrder(StrictModel):
    id: Identifier
    product_id: Identifier
    product_name: str
    quantity: int = Field(ge=0, le=10000)
    daily_demand: int = Field(ge=0, le=10000)
    daily_capacity: int = Field(ge=0, le=10000)
    start_day: int = Field(ge=0, le=29)
    due_day: int = Field(ge=0, le=60)
    amount_cny: Cost


class Supply(StrictModel):
    id: Identifier
    material_id: Identifier
    source_site_id: Identifier
    via_site_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    receipt_per_day: Qty
    capacity_per_day: Qty


class Inbound(StrictModel):
    id: Identifier
    material_id: Identifier
    quantity: Qty
    arrival_day: int = Field(ge=0, le=60)
    via_site_ids: list[Identifier] = Field(default_factory=list, max_length=8)


class Disruption(StrictModel):
    id: Identifier
    name: str = Field(max_length=120)
    site_ids: list[Identifier] = Field(min_length=1, max_length=8)
    start_day: int = Field(default=0, ge=0, le=29)
    duration_days: int = Field(default=7, ge=0, le=30)
    recovery_days: int = Field(default=0, ge=0, le=30)
    capacity_ratio: Decimal = Field(
        default=0, ge=0, le=1, decimal_places=4, allow_inf_nan=False
    )


class MeasureOption(StrictModel):
    id: Identifier
    name: str = Field(max_length=120)
    kind: Literal["alternative", "transfer", "expedite", "reroute"]
    material_id: Identifier
    source_site_id: Identifier
    via_site_ids: list[Identifier] = Field(default_factory=list, max_length=8)
    certified: bool = True
    limit_quantity: Qty
    lead_days: int = Field(ge=0, le=30)
    unit_cost_cny: Cost
    fixed_cost_cny: Cost
    lot_id: Identifier | None = None
    resource_id: Identifier
    description: str


class SimulationConfig(StrictModel):
    version: str
    preset_id: str
    scenario_id: str
    as_of: datetime
    horizon_days: int = Field(ge=1, le=30)
    materials: list[Inventory] = Field(min_length=1, max_length=16)
    bom: dict[str, list[Component]] = Field(min_length=1, max_length=32)
    orders: list[ProductionOrder] = Field(min_length=1, max_length=20)
    supplies: list[Supply] = Field(max_length=32)
    inbounds: list[Inbound] = Field(max_length=16)
    events: list[Disruption] = Field(max_length=8)
    options: list[MeasureOption] = Field(max_length=24)
    assumptions: list[str]

    @model_validator(mode="after")
    def integrity(self):
        if self.as_of.utcoffset() is None:
            raise ValueError("as_of must include timezone")
        for name in [
            "materials",
            "orders",
            "supplies",
            "inbounds",
            "events",
            "options",
        ]:
            ids = [x.id for x in getattr(self, name)]
            if len(ids) != len(set(ids)):
                raise ValueError(f"duplicate {name} id")
        materials = {m.id for m in self.materials}
        lots = {lot.id: lot for lot in self.inbounds}
        if materials.intersection(self.bom):
            raise ValueError("leaf materials cannot also be BOM assemblies")
        for parent, children in self.bom.items():
            if not children or len(children) > 8:
                raise ValueError("BOM must have 1..8 children")
            ids = [c.component_id for c in children]
            if len(ids) != len(set(ids)):
                raise ValueError("duplicate BOM child; combine quantities explicitly")
            if not set(ids) <= materials | self.bom.keys():
                raise ValueError("unknown BOM component")
        visiting, memo = set(), {}

        def expand(node):
            if node in materials:
                return {node: Decimal(1)}
            if node in visiting:
                raise ValueError("BOM cycle detected")
            if node in memo:
                return memo[node]
            visiting.add(node)
            result = {}
            for child in self.bom[node]:
                for material, qty in expand(child.component_id).items():
                    result[material] = (
                        result.get(material, Decimal(0)) + qty * child.quantity
                    )
                    if result[material] > 10000:
                        raise ValueError("expanded BOM quantity exceeds bound")
            visiting.remove(node)
            memo[node] = result
            return result

        for node in self.bom:
            quantities = expand(node)
            if any(
                qty != qty.quantize(Decimal("0.0001")) for qty in quantities.values()
            ):
                raise ValueError(
                    "expanded BOM must use the 0.0001 material unit precision"
                )
        if any(o.product_id not in self.bom for o in self.orders):
            raise ValueError("unknown order product")
        for supply in self.supplies:
            if (
                supply.material_id not in materials
                or supply.receipt_per_day > supply.capacity_per_day
            ):
                raise ValueError(
                    "supply exceeds capacity or references unknown material"
                )
        for lot in self.inbounds:
            if lot.material_id not in materials:
                raise ValueError("unknown inbound material")
        for option in self.options:
            if option.material_id not in materials:
                raise ValueError("unknown option material")
            if option.kind in {"expedite", "reroute"}:
                lot = lots.get(option.lot_id)
                if not lot or lot.material_id != option.material_id:
                    raise ValueError(
                        "transport measure must reference existing matching lot"
                    )
        # Options sharing a resource must agree on its physical capacity/stock.
        resources = {}
        for option in self.options:
            signature = (option.kind, option.limit_quantity, option.material_id)
            if (
                option.resource_id in resources
                and resources[option.resource_id] != signature
            ):
                raise ValueError("inconsistent shared measure resource")
            resources[option.resource_id] = signature
        return self


class MaterialOverride(StrictModel):
    material_id: Identifier
    initial_stock: Qty


class SupplyOverride(StrictModel):
    supply_id: Identifier
    receipt_per_day: Qty


class InboundOverride(StrictModel):
    lot_id: Identifier
    arrival_day: int = Field(ge=0, le=60)


class EventOverride(StrictModel):
    event_id: Identifier
    start_day: int = Field(default=0, ge=0, le=29)
    duration_days: int = Field(default=7, ge=0, le=30)
    recovery_days: int = Field(default=0, ge=0, le=30)
    capacity_ratio: Decimal = Field(
        default=0, ge=0, le=1, decimal_places=4, allow_inf_nan=False
    )


class Measure(StrictModel):
    option_id: Identifier
    quantity: Qty = Decimal(1)
    start_day: int = Field(default=0, ge=0, le=29)
    duration_days: int = Field(default=7, ge=1, le=30)


class SimulationRequest(StrictModel):
    scenario_id: Identifier = "port-congestion"
    preset_id: Literal["manufacturing", "hand-check"] = "manufacturing"
    at_time: datetime | None = None
    event_ids: list[Identifier] | None = Field(default=None, max_length=8)
    horizon_days: int = Field(default=14, ge=1, le=30)
    demand_percent: int = Field(default=100, ge=0, le=300)
    material_overrides: list[MaterialOverride] = Field(
        default_factory=list, max_length=16
    )
    supply_overrides: list[SupplyOverride] = Field(default_factory=list, max_length=32)
    inbound_overrides: list[InboundOverride] = Field(
        default_factory=list, max_length=16
    )
    event_overrides: list[EventOverride] = Field(default_factory=list, max_length=8)
    measures: list[Measure] = Field(default_factory=list, max_length=6)


class Plan(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=60)
    measures: list[Measure] = Field(min_length=1, max_length=6)


class ComparisonRequest(StrictModel):
    simulation: SimulationRequest
    plans: list[Plan] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def unique_plans(self):
        if self.simulation.measures:
            raise ValueError("comparison baseline must have no measures")
        ids = [p.id for p in self.plans]
        if len(ids) != len(set(ids)) or "baseline" in ids:
            raise ValueError("duplicate or reserved plan id")
        return self
