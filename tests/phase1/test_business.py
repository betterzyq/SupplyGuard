from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.business.dataset import ManufacturingDataset, load_dataset
from packages.business.overview import business_overview
from tests.phase1.test_policy import context


@pytest.mark.parametrize(
    "scenario_id,expected_amount,expected_pending",
    [
        ("port-congestion", "3380000.00", 2),
        ("tier2-shutdown", "3860000.00", 3),
        ("regional-flood", "1780000.00", 3),
    ],
)
def test_hand_computed_exposure_and_pending(
    scenario_id, expected_amount, expected_pending
):
    result = business_overview(context(), scenario_id)
    assert result["metrics"]["exposure_amount_cny"] == expected_amount
    assert result["metrics"]["pending_high_risk_orders"] == expected_pending
    assert len(result["orders"]) == len({o["id"] for o in result["orders"]})
    assert Decimal(expected_amount) == sum(
        Decimal(o["amount_cny"]) for o in result["orders"]
    )
    assert all(o["status"] not in {"delivered", "cancelled"} for o in result["orders"])
    assert result["provenance"]["source_type"] == "synthetic"
    assert result["capabilities"]["trained_prediction"] == "manufacturing_not_validated"
    assert result["capabilities"]["public_prediction"] == "historical_validation_p4"


def test_multiple_events_do_not_double_count_order():
    result = business_overview(context())
    order = next(o for o in result["orders"] if o["id"] == "SG-2026-0001")
    assert len(order["risk_event_ids"]) == 2
    assert result["metrics"]["at_risk_orders"] == 4
    assert result["metrics"]["critical_materials"] == 6 - 1


def test_empty_scenario_and_exact_decimal_arithmetic():
    data = load_dataset().model_dump(mode="json")
    for order in data["orders"]:
        order["status"] = "delivered"
    result = business_overview(
        context(), dataset=ManufacturingDataset.model_validate(data)
    )
    assert result["metrics"]["exposure_amount_cny"] == "0.00"
    assert result["metrics"]["at_risk_orders"] == 0
    data["orders"][0].update(status="pending", amount_cny="0.10")
    data["orders"][1].update(status="pending", amount_cny="0.20")
    result = business_overview(
        context(), dataset=ManufacturingDataset.model_validate(data)
    )
    assert result["metrics"]["exposure_amount_cny"] == "0.30"


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate",
        "reference",
        "coordinate",
        "future",
        "negative",
        "precision",
        "timezone",
    ],
)
def test_bad_fixtures_rejected(defect):
    data = load_dataset().model_dump(mode="json")
    if defect == "duplicate":
        data["orders"].append(data["orders"][0])
    elif defect == "reference":
        data["shipments"][0]["order_ids"] = ["missing"]
    elif defect == "coordinate":
        data["sites"][0]["latitude"] = 100
    elif defect == "future":
        data["risk_events"][0]["detected_at"] = "2099-01-01T00:00:00+08:00"
    elif defect == "negative":
        data["orders"][0]["amount_cny"] = "-1"
    elif defect == "precision":
        data["orders"][0]["amount_cny"] = "0.001"
    else:
        data["as_of"] = "2026-10-16T09:00:00"
    with pytest.raises(ValidationError):
        ManufacturingDataset.model_validate(data)


def test_no_context_bypass_or_unknown_scenario():
    with pytest.raises(PermissionError):
        business_overview(context("external_supplier"))
    with pytest.raises(KeyError):
        business_overview(context(), "../../.env")
