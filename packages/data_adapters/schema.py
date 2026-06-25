"""Standard schemas for external data adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

NORMALIZED_TABLE_NAMES: tuple[str, ...] = (
    "suppliers",
    "facilities",
    "materials",
    "products",
    "customers",
    "orders",
    "deliveries",
    "risk_events",
    "quality_issues",
    "supplier_material_edges",
    "material_product_edges",
    "product_order_edges",
    "order_customer_edges",
    "supplier_alternative_edges",
    "country_risk_scores",
    "compliance_entities",
)

NORMALIZED_COLUMNS: dict[str, list[str]] = {
    "suppliers": [
        "supplier_id",
        "supplier_code",
        "supplier_name",
        "country",
        "city",
        "latitude",
        "longitude",
        "tier",
        "risk_score",
        "status",
        "source_dataset",
    ],
    "facilities": [
        "facility_id",
        "supplier_id",
        "facility_name",
        "country",
        "city",
        "latitude",
        "longitude",
        "facility_type",
        "source_dataset",
    ],
    "materials": [
        "material_id",
        "material_code",
        "material_name",
        "category",
        "is_critical",
        "source_dataset",
    ],
    "products": [
        "product_id",
        "product_code",
        "product_name",
        "category",
        "source_dataset",
    ],
    "customers": [
        "customer_id",
        "customer_name",
        "country",
        "region",
        "tier",
        "source_dataset",
    ],
    "orders": [
        "order_id",
        "order_no",
        "supplier_id",
        "product_id",
        "customer_id",
        "order_date",
        "expected_delivery_date",
        "actual_delivery_date",
        "quantity",
        "order_status",
        "source_dataset",
    ],
    "deliveries": [
        "delivery_id",
        "order_id",
        "supplier_id",
        "shipment_mode",
        "origin_country",
        "destination_country",
        "planned_date",
        "actual_date",
        "delay_days",
        "delay_reason",
        "delivery_status",
        "freight_cost",
        "source_dataset",
    ],
    "risk_events": [
        "risk_event_id",
        "supplier_id",
        "country",
        "event_type",
        "severity",
        "title",
        "description",
        "source",
        "detected_at",
        "source_dataset",
    ],
    "quality_issues": [
        "quality_issue_id",
        "supplier_id",
        "material_id",
        "product_id",
        "severity",
        "title",
        "description",
        "detected_at",
        "source_dataset",
    ],
    "supplier_material_edges": [
        "supplier_id",
        "material_id",
        "relationship_type",
        "lead_time_days",
        "risk_weight",
        "source_dataset",
    ],
    "material_product_edges": [
        "material_id",
        "product_id",
        "relationship_type",
        "quantity",
        "is_critical",
        "source_dataset",
    ],
    "product_order_edges": [
        "product_id",
        "order_id",
        "relationship_type",
        "source_dataset",
    ],
    "order_customer_edges": [
        "order_id",
        "customer_id",
        "relationship_type",
        "source_dataset",
    ],
    "supplier_alternative_edges": [
        "supplier_id",
        "alternative_supplier_id",
        "material_id",
        "similarity_score",
        "certified",
        "source_dataset",
    ],
    "country_risk_scores": [
        "country",
        "logistics_risk_score",
        "geopolitical_risk_score",
        "compliance_risk_score",
        "source",
        "source_dataset",
    ],
    "compliance_entities": [
        "entity_id",
        "entity_name",
        "entity_type",
        "country",
        "program",
        "match_status",
        "source_dataset",
    ],
}


def empty_tables() -> dict[str, pd.DataFrame]:
    return {name: pd.DataFrame(columns=NORMALIZED_COLUMNS[name]) for name in NORMALIZED_TABLE_NAMES}


def empty_normalized(name: str = "empty") -> NormalizedDataset:
    return NormalizedDataset(dataset_name=name, tables=empty_tables())


@dataclass
class DatasetProfile:
    dataset_name: str
    file_paths: list[str] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    columns: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class RawDataset:
    dataset_name: str
    frames: dict[str, pd.DataFrame] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NormalizedDataset:
    dataset_name: str
    tables: dict[str, pd.DataFrame] = field(default_factory=empty_tables)

    def table(self, name: str) -> pd.DataFrame:
        return self.tables.get(name, pd.DataFrame(columns=NORMALIZED_COLUMNS.get(name, [])))


@dataclass
class ValidationReport:
    dataset_name: str
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)
