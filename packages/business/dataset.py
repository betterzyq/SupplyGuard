"""Versioned, validated synthetic fixtures; never read a client-supplied path."""

from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DATASET_PATH = Path(__file__).resolve().parents[2] / "data/demo/manufacturing-v1.json"
Severity = Literal["medium", "high", "critical"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Site(Record):
    kind: Literal["factory", "warehouse", "port", "supplier"]
    longitude: float = Field(ge=-180, le=180)
    latitude: float = Field(ge=-90, le=90)
    country: str


class Supplier(Record):
    tier: int = Field(ge=1, le=5)
    site_id: str


class Material(Record):
    critical: bool
    supplier_ids: list[str] = Field(min_length=1)


class Product(Record):
    material_ids: list[str] = Field(min_length=1)


class Order(Record):
    product_id: str
    supplier_id: str
    destination_site_id: str
    customer: str
    amount_cny: Decimal = Field(gt=0, decimal_places=2, max_digits=14)
    promised_at: datetime
    status: Literal["pending", "in_transit", "delivered", "cancelled"]
    action_status: Literal["open", "in_progress", "resolved"]


class Shipment(Record):
    order_ids: list[str] = Field(min_length=1)
    origin_site_id: str
    destination_site_id: str
    mode: Literal["ocean", "road", "rail", "air"]
    eta: datetime


class RiskEvent(Record):
    kind: Literal["port_congestion", "supplier_shutdown", "regional_flood"]
    severity: Severity
    site_ids: list[str] = Field(min_length=1)
    affected_order_ids: list[str] = Field(min_length=1)
    description: str
    detected_at: datetime


class Scenario(Record):
    description: str
    risk_event_ids: list[str] = Field(min_length=1)
    decision_question: str


class ManufacturingDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"]
    dataset_version: str
    source_type: Literal["synthetic"]
    as_of: datetime
    company_name: str
    sites: list[Site] = Field(min_length=1)
    suppliers: list[Supplier] = Field(min_length=1)
    materials: list[Material] = Field(min_length=1)
    products: list[Product] = Field(min_length=1)
    orders: list[Order] = Field(min_length=1)
    shipments: list[Shipment] = Field(min_length=1)
    risk_events: list[RiskEvent] = Field(min_length=1)
    scenarios: list[Scenario] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_integrity(self):
        tables = {
            name: getattr(self, name)
            for name in (
                "sites",
                "suppliers",
                "materials",
                "products",
                "orders",
                "shipments",
                "risk_events",
                "scenarios",
            )
        }
        ids = {}
        for name, rows in tables.items():
            ids[name] = {r.id for r in rows}
            if len(ids[name]) != len(rows):
                raise ValueError(f"duplicate id in {name}")

        def refs(values, target):
            if not set(values).issubset(ids[target]):
                raise ValueError(f"invalid reference to {target}")
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate reference to {target}")

        if self.as_of.utcoffset() is None:
            raise ValueError("as_of must include timezone")
        for row in self.suppliers:
            refs([row.site_id], "sites")
        for row in self.materials:
            refs(row.supplier_ids, "suppliers")
        for row in self.products:
            refs(row.material_ids, "materials")
        for row in self.orders:
            refs([row.product_id], "products")
            refs([row.supplier_id], "suppliers")
            refs([row.destination_site_id], "sites")
            if row.promised_at.utcoffset() is None:
                raise ValueError("promised_at must include timezone")
        for row in self.shipments:
            refs(row.order_ids, "orders")
            refs([row.origin_site_id, row.destination_site_id], "sites")
            if row.eta.utcoffset() is None:
                raise ValueError("eta must include timezone")
        for row in self.risk_events:
            refs(row.site_ids, "sites")
            refs(row.affected_order_ids, "orders")
            if row.detected_at.utcoffset() is None or row.detected_at > self.as_of:
                raise ValueError("risk event cannot be in the future or lack timezone")
        for row in self.scenarios:
            refs(row.risk_event_ids, "risk_events")
        return self


@lru_cache(maxsize=1)
def load_dataset() -> ManufacturingDataset:
    return ManufacturingDataset.model_validate_json(
        DATASET_PATH.read_text(encoding="utf-8")
    )
