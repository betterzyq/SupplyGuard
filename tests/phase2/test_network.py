from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.business.network import (
    ReplayDataset,
    clip_trace,
    load_replay,
    network_snapshot,
)
from tests.phase1.test_policy import context


def at(hour, minute=0):
    return datetime.fromisoformat(f"2026-10-16T{hour:02}:{minute:02}:00+08:00")


@pytest.mark.parametrize(
    "hour,exposure,event_count",
    [
        (0, "0.00", 0),
        (5, "0.00", 0),
        (6, "3100000.00", 1),
        (8, "3380000.00", 2),
        (9, "3380000.00", 2),
    ],
)
def test_clock_hides_future_events_and_aggregates(hour, exposure, event_count):
    result = network_snapshot(context(), at_time=at(hour))
    assert result["metrics"]["exposure_amount_cny"] == exposure
    assert len(result["risk_events"]) == event_count
    assert all(
        datetime.fromisoformat(e["detected_at"]) <= at(hour)
        for e in result["risk_events"]
    )
    for ship in result["shipments"]:
        assert all(datetime.fromisoformat(p["at"]) <= at(hour) for p in ship["trace"])
        assert ship["position"] == ship["trace"][-1]
        assert all(
            m["observed_at"] is None
            or datetime.fromisoformat(m["observed_at"]) <= at(hour)
            for m in ship["milestones"]
        )
        assert all(
            datetime.fromisoformat(u["observed_at"]) <= at(hour)
            for u in ship["eta_updates"]
        )
        if hour < 6:
            assert ship["eta"] == ship["planned_eta"] and ship["delay_hours"] == 0


def test_trace_interpolation_has_no_future_waypoint():
    points = load_replay().journeys[0].trace
    result = clip_trace(points, at(4, 30))
    left, right = points[2], points[3]
    assert datetime.fromisoformat(result[-1]["at"]) == at(4, 30)
    assert result[-1]["longitude"] == pytest.approx(
        (left.longitude + right.longitude) / 2
    )
    assert result[-1]["latitude"] == pytest.approx((left.latitude + right.latitude) / 2)
    assert clip_trace(points, points[0].at - timedelta(minutes=1)) == []


@pytest.mark.parametrize(
    "filters",
    [
        dict(supplier_id="V-001"),
        dict(mode="ocean"),
        dict(q="SHP-003"),
        dict(risk_only=True),
        dict(q="no-match"),
        dict(mode="road", risk_only=True),
    ],
)
def test_filters_keep_map_orders_shipments_and_money_consistent(filters):
    data = network_snapshot(context(), **filters)
    ids = {o["id"] for o in data["orders"]}
    assert all(set(s["order_ids"]) <= ids for s in data["shipments"])
    exposed = [o for o in data["orders"] if o["risk_event_ids"]]
    assert Decimal(data["metrics"]["exposure_amount_cny"]) == sum(
        (Decimal(o["amount_cny"]) for o in exposed), Decimal(0)
    )
    assert data["metrics"]["visible_orders"] == len(ids)
    assert data["metrics"]["visible_sites"] == len(data["sites"])
    assert data["metrics"]["visible_shipments"] == len(data["shipments"])
    if filters.get("mode"):
        assert all(s["mode"] == filters["mode"] for s in data["shipments"])
    if filters.get("supplier_id"):
        assert all(o["supplier_id"] == filters["supplier_id"] for o in data["orders"])
    if filters.get("q") == "no-match":
        assert (
            data["sites"]
            == data["shipments"]
            == data["orders"]
            == data["risk_events"]
            == []
        )


def test_dependency_paths_share_the_manufacturing_order_and_materials():
    data = network_snapshot(context())
    order = next(o for o in data["orders"] if o["id"] == "SG-2026-0001")
    assert any(
        p["nodes"][0]["id"] == "V-003" and p["nodes"][1]["id"] == "MAT-03"
        for p in order["dependency_paths"]
    )
    for path in order["dependency_paths"]:
        assert [n["type"] for n in path["nodes"]] == [
            "Supplier",
            "Material",
            "Product",
            "Order",
            "Customer",
        ]
        assert path["nodes"][3]["id"] == order["id"]
    for area in data["risk_areas"]:
        assert area["polygon"][0] == area["polygon"][-1]


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 10, 16, 3),
        at(0) - timedelta(minutes=1),
        at(9) + timedelta(minutes=1),
    ],
)
def test_invalid_or_future_replay_rejected(value):
    with pytest.raises(ValueError):
        network_snapshot(context(), at_time=value)


def test_unknown_entities_and_retired_role_denied():
    with pytest.raises(PermissionError):
        network_snapshot(context("external_supplier"))
    with pytest.raises(KeyError):
        network_snapshot(context(), scenario_id="unknown")
    with pytest.raises(KeyError):
        network_snapshot(context(), supplier_id="unknown")


@pytest.mark.parametrize(
    "defect",
    [
        "wrong-shipment",
        "endpoint",
        "coordinate",
        "trace-order",
        "future-trace",
        "naive-trace",
        "future-update",
        "missing-radius",
    ],
)
def test_invalid_replay_fixtures_fail_early(defect):
    data = load_replay().model_dump(mode="json")
    journey = data["journeys"][0]
    if defect == "wrong-shipment":
        journey["shipment_id"] = "absent"
    elif defect == "endpoint":
        journey["route"][0] = [0, 0]
    elif defect == "coordinate":
        journey["route"][1] = [200, 30]
    elif defect == "trace-order":
        journey["trace"].reverse()
    elif defect == "future-trace":
        journey["trace"][-1]["at"] = "2026-10-16T12:00:00+08:00"
    elif defect == "naive-trace":
        journey["trace"][0]["at"] = "2026-10-15T18:00:00"
    elif defect == "future-update":
        journey["eta_updates"][0]["observed_at"] = "2026-10-16T12:00:00+08:00"
    else:
        data["risk_radius_km"] = {}
    with pytest.raises(ValidationError):
        ReplayDataset.model_validate(data)
