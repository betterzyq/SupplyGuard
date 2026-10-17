from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.business.simulation import (
    build_config,
    event_factor,
    run_simulation,
    simulate,
)
from packages.business.simulation_models import (
    Disruption,
    Measure,
    SimulationConfig,
    SimulationRequest,
)
from tests.phase1.test_policy import context


def hand(duration=7, stock=100, **kwargs):
    request = SimulationRequest(
        preset_id="hand-check",
        event_overrides=[
            {"event_id": i, "duration_days": duration}
            for i in ["EVT-PORT", "EVT-PORT-SECONDARY"]
        ],
        material_overrides=[{"material_id": "MAT-01", "initial_stock": stock}],
        **kwargs,
    )
    return build_config(request)


@pytest.mark.parametrize(
    "duration,first,peak,completion,late", [(3, None, "0", 9, 0), (7, 5, "40", 11, 1)]
)
def test_hand_calculated_stock_and_delivery(duration, first, peak, completion, late):
    result = simulate(hand(duration))
    material = result["materials"][0]
    assert material["first_shortage_day"] == first
    assert material["peak_shortage_units"] == peak
    assert material["initial_buffer_days"] == "5"
    assert result["metrics"]["last_completion_day"] == completion
    assert result["metrics"]["delayed_orders"] == late
    assert result["metrics"]["delayed_order_amount_cny"] == (
        "1280000.00" if late else "0.00"
    )
    assert [d["closing_stock"] for d in material["daily"][:3]] == ["80", "60", "40"]


def test_stock_conservation_every_material_day_and_no_negative_inventory():
    for scenario in ["port-congestion", "tier2-shutdown", "regional-flood"]:
        config = build_config(SimulationRequest(scenario_id=scenario))
        for material in simulate(config)["materials"]:
            for row in material["daily"]:
                assert Decimal(row["closing_stock"]) == sum(
                    Decimal(row[k])
                    for k in [
                        "opening_stock",
                        "regular_receipts",
                        "inbound_receipts",
                        "measure_receipts",
                    ]
                ) - Decimal(row["consumption"])
                assert Decimal(row["closing_stock"]) >= 0


def test_more_inventory_and_effective_supply_do_not_worsen_single_material_case():
    results = [simulate(hand(stock=stock)) for stock in [60, 100, 140, 200]]
    first = [r["materials"][0]["first_shortage_day"] for r in results]
    assert [f if f is not None else 999 for f in first] == sorted(
        f if f is not None else 999 for f in first
    )
    peaks = [Decimal(r["materials"][0]["peak_shortage_units"]) for r in results]
    assert peaks == sorted(peaks, reverse=True)
    proposed = simulate(
        hand(), [Measure(option_id="alternative-MAT-01", quantity=20, duration_days=7)]
    )
    assert proposed["metrics"]["delayed_orders"] == 0
    assert proposed["metrics"]["incremental_cost_cny"] == "4500.00"
    assert proposed["materials"][0]["peak_shortage_units"] == "0"
    transfer = simulate(
        hand(), [Measure(option_id="transfer-MAT-01", quantity=80, duration_days=1)]
    )
    assert transfer["metrics"]["delayed_orders"] == 0
    assert transfer["metrics"]["incremental_cost_cny"] == "1140.00"


def test_overlapping_events_use_minimum_capacity_not_sum_or_product():
    config = hand()
    config.events[0].capacity_ratio = Decimal("0.5")
    config.events[1].capacity_ratio = Decimal("0.5")
    result = simulate(config)
    assert result["materials"][0]["daily"][0]["regular_receipts"] == "10"
    assert result["metrics"]["delayed_order_amount_cny"] in ["0.00", "1280000.00"]
    event = Disruption(
        id="E", name="E", site_ids=["X"], duration_days=3, recovery_days=2
    )
    assert [event_factor(event, d) for d in [2, 3, 4, 5]] == [
        0,
        Decimal(1) / 3,
        Decimal(2) / 3,
        1,
    ]


def test_no_events_and_zero_demand_have_no_synthetic_shortages():
    normal = simulate(build_config(SimulationRequest(event_ids=[])))
    assert normal["metrics"]["delayed_orders"] == 0
    zero = simulate(hand(demand_percent=0))
    assert zero["metrics"]["delayed_orders"] == 0
    assert zero["materials"][0]["first_shortage_day"] is None
    assert zero["materials"][0]["initial_buffer_days"] is None


def test_multiple_bom_paths_sum_material_use_but_not_order_money():
    config = hand()
    data = config.model_dump(mode="json")
    product = config.orders[0].product_id
    data["bom"] = {
        product: [
            {"component_id": "ASM-A", "quantity": "1"},
            {"component_id": "ASM-B", "quantity": "1"},
        ],
        "ASM-A": [{"component_id": "MAT-01", "quantity": "1"}],
        "ASM-B": [{"component_id": "MAT-01", "quantity": "1"}],
    }
    result = simulate(SimulationConfig.model_validate(data))
    assert result["orders"][0]["evidence"][0]["units_per_product"] == "2"
    assert len(result["orders"][0]["evidence"][0]["bom_paths"]) == 2
    assert result["metrics"]["delayed_orders"] == 1
    assert result["metrics"]["delayed_order_amount_cny"] == "1280000.00"


@pytest.mark.parametrize(
    "defect",
    [
        "cycle",
        "unknown",
        "duplicate-child",
        "negative-stock",
        "negative-cost",
        "capacity",
        "NaN",
        "unknown-lot",
    ],
)
def test_invalid_input_rejected(defect):
    data = hand().model_dump(mode="json")
    product = next(iter(data["bom"]))
    if defect == "cycle":
        data["bom"][product][0]["component_id"] = product
    elif defect == "unknown":
        data["bom"][product][0]["component_id"] = "missing"
    elif defect == "duplicate-child":
        data["bom"][product].append(data["bom"][product][0])
    elif defect == "negative-stock":
        data["materials"][0]["initial_stock"] = "-1"
    elif defect == "negative-cost":
        data["options"][0]["unit_cost_cny"] = "-1"
    elif defect == "capacity":
        data["supplies"][0]["receipt_per_day"] = "100000"
    elif defect == "NaN":
        data["materials"][0]["initial_stock"] = "NaN"
    elif defect == "unknown-lot":
        data["options"][0].update(kind="expedite", lot_id="missing")
    with pytest.raises(ValidationError):
        SimulationConfig.model_validate(data)


@pytest.mark.parametrize(
    "measure",
    [
        {"option_id": "missing"},
        {"option_id": "alternative-MAT-01-uncertified", "quantity": 10},
        {"option_id": "alternative-MAT-01", "quantity": 61},
        {"option_id": "transfer-MAT-01", "quantity": 101, "duration_days": 1},
        {"option_id": "transfer-MAT-01", "quantity": 10, "duration_days": 2},
        {"option_id": "alternative-MAT-01", "quantity": 0},
        {"option_id": "expedite-MAT-01", "quantity": 2, "duration_days": 1},
    ],
)
def test_infeasible_measures_rejected(measure):
    config = build_config(SimulationRequest())
    with pytest.raises(ValueError):
        simulate(config, [Measure(**measure)])


def test_no_duplicate_existing_inbound_and_no_conflicting_transport():
    config = build_config(SimulationRequest())
    reroute = Measure(option_id="reroute-MAT-01", quantity=1, duration_days=1)
    result = simulate(config, [reroute])
    mat = next(m for m in result["materials"] if m["id"] == "MAT-01")
    assert sum(Decimal(d["inbound_receipts"]) for d in mat["daily"]) == 80
    assert mat["daily"][2]["inbound_receipts"] == "80"
    assert result["metrics"]["incremental_cost_cny"] == "2800.00"
    with pytest.raises(ValueError):
        simulate(
            config,
            [
                reroute,
                Measure(option_id="expedite-MAT-01", quantity=1, duration_days=1),
            ],
        )
    with pytest.raises(ValueError):
        simulate(config, [reroute, reroute])


def test_ineffective_expedite_still_has_explicit_cost():
    config = build_config(SimulationRequest())
    result = simulate(
        config, [Measure(option_id="expedite-MAT-01", quantity=1, duration_days=1)]
    )
    assert result["metrics"]["incremental_cost_cny"] == "2000.00"
    assert any(
        a.get("lot_id") == "LOT-MAT-01" and a["status"] == "held"
        for a in result["actions"]
    )


def test_late_window_is_censored_not_assumed_delayed_and_result_reproducible():
    user = context()
    req = SimulationRequest(preset_id="hand-check", horizon_days=3)
    first = run_simulation(user, req)
    assert first == run_simulation(user, req)
    assert first["result"]["metrics"]["censored_orders"] == 1
    assert first["result"]["metrics"]["delayed_orders"] == 0
    assert first["run_id"] != run_simulation(context(), req)["run_id"]


def test_future_event_and_excessive_regular_supply_rejected():
    with pytest.raises(ValueError):
        build_config(
            SimulationRequest(
                at_time="2026-10-16T02:00:00+08:00", event_ids=["EVT-PORT"]
            )
        )
    with pytest.raises(ValueError):
        build_config(
            SimulationRequest(
                supply_overrides=[{"supply_id": "LANE-MAT-01", "receipt_per_day": 100}]
            )
        )
    with pytest.raises(ValueError):
        build_config(
            SimulationRequest(
                material_overrides=[{"material_id": "MAT-01", "initial_stock": 0}] * 2
            )
        )


def test_shared_transfer_stock_and_daily_alternative_capacity_are_not_reused():
    for kind, qty in [("transfer", 60), ("alternative", 40)]:
        data = hand().model_dump(mode="json")
        option = next(
            o for o in data["options"] if o["kind"] == kind and o["certified"]
        )
        alias = {**option, "id": "shared-alias"}
        data["options"].append(alias)
        config = SimulationConfig.model_validate(data)
        with pytest.raises(ValueError):
            simulate(
                config,
                [
                    Measure(option_id=option["id"], quantity=qty, duration_days=1),
                    Measure(option_id=alias["id"], quantity=qty, duration_days=1),
                ],
            )


def test_fractional_bom_consumption_conserves_inventory():
    data = hand(stock=101).model_dump(mode="json")
    root = next(iter(data["bom"]))
    data["bom"][root][0]["quantity"] = "0.25"
    result = simulate(SimulationConfig.model_validate(data))
    for row in result["materials"][0]["daily"]:
        assert Decimal(row["opening_stock"]) + Decimal(
            row["regular_receipts"]
        ) - Decimal(row["consumption"]) == Decimal(row["closing_stock"])
    data["bom"] = {
        root: [{"component_id": "ASM", "quantity": "0.0001"}],
        "ASM": [{"component_id": "MAT-01", "quantity": "0.0001"}],
    }
    with pytest.raises(ValidationError):
        SimulationConfig.model_validate(data)


def test_production_capacity_and_censored_orders_are_explicit():
    config = hand(stock=10000)
    config.orders[0].daily_capacity = 5
    result = simulate(config)
    assert result["orders"][0]["capacity_limited_days"]
    assert result["orders"][0]["evidence"] == []
    assert result["metrics"]["incomplete_orders"] == 1
    zero = simulate(hand(demand_percent=0, horizon_days=1))
    assert zero["metrics"]["censored_orders"] == 0


def test_short_window_does_not_add_free_late_arrivals_or_cost():
    config = hand(horizon_days=1)
    result = simulate(
        config, [Measure(option_id="transfer-MAT-01", quantity=80, duration_days=1)]
    )
    assert result["metrics"]["incremental_cost_cny"] == "0.00"
    assert result["actions"][0]["status"] == "outside_window"
    assert result["materials"][0]["daily"][0]["measure_receipts"] == "0"


def test_equivalent_timezones_have_same_business_day_and_snapshot():
    user = context()
    a = run_simulation(user, SimulationRequest(at_time="2026-10-16T02:00:00+08:00"))
    b = run_simulation(user, SimulationRequest(at_time="2026-10-15T18:00:00Z"))
    assert a == b
    assert a["result"]["materials"][0]["daily"][0]["date"] == "2026-10-16"


def test_snapshot_contains_replayable_original_request():
    user = context()
    request = SimulationRequest(
        preset_id="hand-check",
        demand_percent=150,
        material_overrides=[{"material_id": "MAT-01", "initial_stock": "130"}],
    )
    first = run_simulation(user, request)
    assert first == run_simulation(
        user, SimulationRequest.model_validate(first["input_snapshot"]["request"])
    )
