"""Explicit import and command contracts; all timestamps need timezone offsets."""

from decimal import Decimal
from datetime import datetime
import re
from typing import Literal
from uuid import UUID
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    field_serializer,
)

Kind = Literal["site", "order", "shipment", "event", "prediction", "simulation"]
ImportKind = Literal["site", "order", "shipment", "event"]
Source = Literal["synthetic", "enterprise_uploaded"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator(
        "promised_at", "eta", "detected_at", "due_at", mode="before", check_fields=False
    )
    @classmethod
    def explicit_offset(cls, value):
        if (
            not isinstance(value, (str, datetime))
            or isinstance(value, str)
            and not re.search(r"(Z|[+-]\d{2}:\d{2})$", value.strip())
        ):
            raise ValueError("Use an ISO8601 date/time with explicit timezone offset")
        return value


class Item(Strict):
    code: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$")
    name: str = Field(min_length=1, max_length=160)


class SiteRow(Item):
    site_type: Literal["factory", "warehouse", "port", "supplier"]
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    country: str = Field(min_length=2, max_length=60)


class OrderRow(Item):
    destination_site_code: str = Field(min_length=1, max_length=100)
    product_code: str = Field(min_length=1, max_length=100)
    customer: str = Field(min_length=1, max_length=160)
    amount_cny: Decimal = Field(
        gt=0, max_digits=14, decimal_places=2, allow_inf_nan=False
    )
    currency: Literal["CNY"] = "CNY"
    promised_at: AwareDatetime
    status: Literal["pending", "in_transit", "delivered", "cancelled"]

    @field_serializer("amount_cny")
    def money(self, value):
        return f"{value:.2f}"


class ShipmentRow(Item):
    origin_site_code: str = Field(min_length=1, max_length=100)
    destination_site_code: str = Field(min_length=1, max_length=100)
    order_codes: str = Field(min_length=1, max_length=2000)
    mode: Literal["ocean", "road", "rail", "air"]
    eta: AwareDatetime


class EventRow(Item):
    site_codes: str = Field(min_length=1, max_length=2000)
    order_codes: str = Field(min_length=1, max_length=2000)
    severity: Literal["medium", "high", "critical"]
    description: str = Field(min_length=1, max_length=2000)
    detected_at: AwareDatetime


ROWS = {"site": SiteRow, "order": OrderRow, "shipment": ShipmentRow, "event": EventRow}


def references(kind, row):
    if kind == "order":
        return [("site", row["destination_site_code"], "destination")]
    if kind == "shipment":
        return [
            ("site", row["origin_site_code"], "origin"),
            ("site", row["destination_site_code"], "destination"),
        ] + [("order", x, "contains") for x in codes(row["order_codes"])]
    if kind == "event":
        return [("site", x, "located_at") for x in codes(row["site_codes"])] + [
            ("order", x, "affects") for x in codes(row["order_codes"])
        ]
    return []


def codes(value):
    result = [x.strip() for x in value.split(";")]
    if any(not x for x in result) or len(set(result)) != len(result):
        raise ValueError(
            "References must be unique nonempty codes separated by semicolons"
        )
    return result


class TaskCreate(Strict):
    record_id: UUID
    title: str = Field(min_length=1, max_length=160)
    due_at: AwareDatetime
    assignee_id: UUID | None = None
    measures: str = Field(default="", max_length=2000)


class TaskChange(Strict):
    expected_version: int = Field(ge=1)
    action: Literal["assign", "start", "submit", "complete", "reopen", "cancel"]
    assignee_id: UUID | None = None
    measures: str | None = Field(default=None, max_length=2000)
    actual_cost_cny: Decimal | None = Field(
        default=None, ge=0, max_digits=14, decimal_places=2, allow_inf_nan=False
    )
    result: str | None = Field(default=None, max_length=2000)


class Capture(Strict):
    kind: Literal["prediction", "simulation"]
    identifier: str = Field(min_length=1, max_length=100)
    share_with_tenant: Literal[True]


class ReportRequest(Strict):
    kind: Literal["risk", "evaluation"]
    format: Literal["csv", "xlsx"] = "xlsx"
    benchmark_run_id: UUID | None = None


TOPICS = [
    "task.created",
    "task.updated",
    "import.confirmed",
    "record.created",
    "report.created",
]


class SubscriptionCreate(Strict):
    name: str = Field(min_length=1, max_length=100)
    topics: list[str] = Field(min_length=1, max_length=5)

    @field_validator("topics")
    @classmethod
    def topics_known(cls, value):
        if len(set(value)) != len(value) or any(x not in TOPICS for x in value):
            raise ValueError("Unknown or duplicate local event topic")
        return value
