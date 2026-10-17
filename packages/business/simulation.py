"""CPU-only deterministic stock-flow simulation. No LLM or shared infrastructure."""

import hashlib
import json
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.authz.rbac import UserContext
from packages.business.dataset import load_dataset
from packages.business.network import load_replay, parse_time
from packages.business.overview import business_overview
from packages.business.simulation_models import (
    ComparisonRequest,
    Component,
    Disruption,
    Measure,
    SimulationConfig,
    SimulationRequest,
)

ENGINE_VERSION = "daily-stock-flow-3.0.0"
CONFIG_PATH = Path(__file__).resolve().parents[2] / "data/demo/simulation-v1.json"
ZERO = Decimal(0)
ONE = Decimal(1)


def number(value):
    text = format(Decimal(value), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def money(value):
    return format(
        Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f"
    )


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def load_simulation():
    return SimulationConfig.model_validate_json(CONFIG_PATH.read_text())


def build_config(request: SimulationRequest):
    base = load_dataset()
    scenario = next((s for s in base.scenarios if s.id == request.scenario_id), None)
    if not scenario:
        raise KeyError("Unknown scenario")
    at = parse_time(request.at_time, load_replay()).astimezone(
        ZoneInfo("Asia/Shanghai")
    )
    available = [
        e
        for e in base.risk_events
        if e.id in scenario.risk_event_ids and e.detected_at <= at
    ]
    ids = (
        request.event_ids
        if request.event_ids is not None
        else [e.id for e in available]
    )
    if len(ids) != len(set(ids)) or not set(ids) <= {e.id for e in available}:
        raise ValueError("事件必须属于当前场景且在所选时点已发现，不能重复")
    config = load_simulation().model_copy(deep=True)
    config.scenario_id, config.as_of = scenario.id, at
    config.horizon_days, config.preset_id = request.horizon_days, request.preset_id
    config.events = [
        Disruption(id=e.id, name=e.name, site_ids=e.site_ids)
        for e in available
        if e.id in ids
    ]
    if request.preset_id == "hand-check":
        # A complete one-product case with an explicit 100 / 20 / 200 stock-demand plan.
        mat, order, supply = config.materials[0], config.orders[0], config.supplies[0]
        config.materials = [mat]
        config.bom = {order.product_id: [Component(component_id=mat.id, quantity=1)]}
        order.quantity, order.daily_demand, order.daily_capacity = 200, 20, 40
        order.start_day, order.due_day = 0, 9
        config.orders, config.supplies = [order], [supply]
        supply.receipt_per_day, supply.capacity_per_day = Decimal(20), Decimal(90)
        # Make this hand case applicable to each scenario's selected event footprint.
        footprint = [s for e in config.events for s in e.site_ids]
        supply.via_site_ids = list(dict.fromkeys(footprint))
        config.inbounds = []
        config.options = [
            o
            for o in config.options
            if o.material_id == mat.id and o.kind in {"alternative", "transfer"}
        ]
        config.assumptions.insert(
            0,
            "手算样例：单订单 200 件、日需求 20、库存 100、常规到货 20/日、BOM 1:1；需求连续释放 10 天。",
        )
    # Revalidate copies and nested hand-case dictionaries before applying overrides.
    config = SimulationConfig.model_validate(config.model_dump())
    tables = [
        (request.material_overrides, config.materials, "material_id", "initial_stock"),
        (request.supply_overrides, config.supplies, "supply_id", "receipt_per_day"),
        (request.inbound_overrides, config.inbounds, "lot_id", "arrival_day"),
    ]
    for overrides, records, key, field in tables:
        lookup, seen = {r.id: r for r in records}, set()
        for item in overrides:
            identifier = getattr(item, key)
            if identifier not in lookup or identifier in seen:
                raise ValueError("未知或重复的库存/供给/在途覆盖项")
            seen.add(identifier)
            setattr(lookup[identifier], field, getattr(item, field))
    event_lookup, seen = {e.id: e for e in config.events}, set()
    for override in request.event_overrides:
        if override.event_id not in event_lookup or override.event_id in seen:
            raise ValueError("未知或重复的事件覆盖项")
        seen.add(override.event_id)
        for key, value in override.model_dump(exclude={"event_id"}).items():
            setattr(event_lookup[override.event_id], key, value)
    for order in config.orders:
        scale = Decimal(request.demand_percent) / 100
        order.quantity = int(
            (order.quantity * scale).to_integral_value(rounding=ROUND_CEILING)
        )
        order.daily_demand = int(
            (order.daily_demand * scale).to_integral_value(rounding=ROUND_CEILING)
        )
        # Production capacity remains fixed: demand stress must not create capacity.
    return SimulationConfig.model_validate(config.model_dump())


def expand_bom(config):
    leaves = {m.id for m in config.materials}
    memo = {}

    def visit(node):
        if node in leaves:
            return {node: ONE}
        if node not in memo:
            totals = {}
            for child in config.bom[node]:
                for key, qty in visit(child.component_id).items():
                    totals[key] = totals.get(key, ZERO) + child.quantity * qty
            memo[node] = totals
        return memo[node]

    return {o.product_id: visit(o.product_id) for o in config.orders}


def event_factor(event, day):
    elapsed = day - event.start_day
    if elapsed < 0 or event.duration_days == 0:
        return ONE
    if elapsed < event.duration_days:
        return event.capacity_ratio
    recovery = elapsed - event.duration_days
    if recovery < event.recovery_days:
        return event.capacity_ratio + (ONE - event.capacity_ratio) * Decimal(
            recovery + 1
        ) / Decimal(event.recovery_days + 1)
    return ONE


def availability(config, sites, day):
    matches = [
        (event_factor(e, day), e.id)
        for e in config.events
        if set(e.site_ids).intersection(sites)
    ]
    return min([x[0] for x in matches], default=ONE), [i for f, i in matches if f < ONE]


def validate_measures(config, measures):
    options = {o.id: o for o in config.options}
    seen, occupied_lots, resources = set(), set(), {}
    for measure in measures:
        option = options.get(measure.option_id)
        if not option or option.id in seen:
            raise ValueError("未知或重复的措施")
        seen.add(option.id)
        if not option.certified:
            raise ValueError("替代供给尚未认证，不可纳入可执行方案")
        if measure.start_day >= config.horizon_days:
            raise ValueError("措施开始时间超出模拟窗口")
        if measure.quantity <= 0 or measure.quantity > option.limit_quantity:
            raise ValueError("措施数量必须为正且不超过供货能力/备援库存上限")
        if option.kind in {"expedite", "reroute"}:
            if measure.quantity != 1 or measure.duration_days != 1:
                raise ValueError("运输措施按整批执行，数量和持续天数必须为 1")
            if option.lot_id in occupied_lots:
                raise ValueError("同一在途批次不能同时加急与改道")
            occupied_lots.add(option.lot_id)
            lot = next(lot for lot in config.inbounds if lot.id == option.lot_id)
            if lot.quantity > option.limit_quantity:
                raise ValueError("运输批次数量超过措施承载上限")
            if measure.start_day > lot.arrival_day:
                raise ValueError("不能重排计划到货日已过的批次")
        key = option.resource_id
        if option.kind == "alternative":
            for day in range(
                measure.start_day,
                min(config.horizon_days, measure.start_day + measure.duration_days),
            ):
                resources[(key, day)] = (
                    resources.get((key, day), ZERO) + measure.quantity
                )
                if resources[(key, day)] > option.limit_quantity:
                    raise ValueError("重叠措施超过共享供货产能")
        elif option.kind == "transfer":
            if measure.duration_days != 1:
                raise ValueError("库存调拨只能按一次性库存执行")
            resources[key] = resources.get(key, ZERO) + measure.quantity
            if resources[key] > option.limit_quantity:
                raise ValueError("重复调拨超过共享备援库存")
    return options


def evidence_paths(config, product, material):
    paths = []

    def visit(node, path, quantity):
        if len(paths) >= 32:
            return
        if node == material:
            paths.append({"nodes": path, "units_per_product": number(quantity)})
        elif node in config.bom:
            for c in config.bom[node]:
                visit(c.component_id, path + [c.component_id], quantity * c.quantity)

    visit(product, [product], ONE)
    return paths


def simulate(config: SimulationConfig, measures: list[Measure] | None = None):
    measures = measures or []
    options = validate_measures(config, measures)
    bom = expand_bom(config)
    materials = {m.id: m for m in config.materials}
    orders = sorted(config.orders, key=lambda o: (o.due_day, o.id))
    stock = {m.id: m.initial_stock for m in config.materials}
    released = {o.id: 0 for o in orders}
    produced = {o.id: 0 for o in orders}
    completed = {o.id: None for o in orders}
    on_due = {o.id: 0 for o in orders}
    blocked_days = {o.id: {} for o in orders}
    capacity_days = {o.id: [] for o in orders}
    material_rows = {m.id: [] for m in config.materials}
    costs, actions, pending_receipts = [], [], []
    adjusted_lots = {}
    for measure in measures:
        option = options[measure.option_id]
        if option.kind in {"expedite", "reroute"}:
            adjusted_lots[option.lot_id] = (measure, option)
    lot_received, billed = set(), set()
    for day in range(config.horizon_days):
        opening = stock.copy()
        regular = {m: ZERO for m in materials}
        inbound = {m: ZERO for m in materials}
        additional = {m: ZERO for m in materials}
        consumed = {m: ZERO for m in materials}
        effects = {m: set() for m in materials}
        for supply in config.supplies:
            factor, events = availability(
                config, [supply.source_site_id, *supply.via_site_ids], day
            )
            qty = (supply.receipt_per_day * factor).quantize(
                Decimal("0.0001"), rounding=ROUND_DOWN
            )
            regular[supply.material_id] += qty
            effects[supply.material_id].update(events)
        for measure in measures:
            option = options[measure.option_id]
            if option.kind not in {"alternative", "transfer"}:
                continue
            active = (
                measure.start_day
                <= day
                < measure.start_day
                + (measure.duration_days if option.kind == "alternative" else 1)
            )
            if not active:
                continue
            arrival = day + option.lead_days
            # No purchases beyond the window are silently counted as free effective stock.
            factor, events = availability(
                config, [option.source_site_id, *option.via_site_ids], day
            )
            qty = (measure.quantity * factor).quantize(
                Decimal("0.0001"), rounding=ROUND_DOWN
            )
            if qty and arrival < config.horizon_days:
                pending_receipts.append((arrival, option.material_id, qty))
                fixed = ZERO if option.id in billed else option.fixed_cost_cny
                costs.append(
                    {
                        "day": day,
                        "option_id": option.id,
                        "quantity": number(qty),
                        "amount_cny": money(qty * option.unit_cost_cny + fixed),
                    }
                )
                billed.add(option.id)
                status = "scheduled"
            else:
                status = (
                    "outside_window" if arrival >= config.horizon_days else "blocked"
                )
            actions.append(
                {
                    "day": day,
                    "option_id": option.id,
                    "status": status,
                    "quantity": number(qty if status == "scheduled" else ZERO),
                    "arrival_day": arrival,
                    "event_ids": events,
                }
            )
        for arrival, material, qty in pending_receipts:
            if arrival == day:
                additional[material] += qty
        for lot in config.inbounds:
            if lot.id in lot_received:
                continue
            adjustment = adjusted_lots.get(lot.id)
            if adjustment:
                measure, option = adjustment
                arrival = measure.start_day + option.lead_days
                # At start-day the existing inbound is rebooked, never duplicated.
                if day == measure.start_day:
                    costs.append(
                        {
                            "day": day,
                            "option_id": option.id,
                            "quantity": number(lot.quantity),
                            "amount_cny": money(
                                lot.quantity * option.unit_cost_cny
                                + option.fixed_cost_cny
                            ),
                        }
                    )
                    actions.append(
                        {
                            "day": day,
                            "option_id": option.id,
                            "status": "rebooked",
                            "lot_id": lot.id,
                            "arrival_day": arrival,
                            "quantity": number(lot.quantity),
                        }
                    )
                sites = [option.source_site_id, *option.via_site_ids]
                # Rebooking in the future cannot hide a lot that arrives before that day.
                if day < measure.start_day:
                    arrival, sites = lot.arrival_day, lot.via_site_ids
            else:
                arrival, sites = lot.arrival_day, lot.via_site_ids
            if day >= arrival:
                factor, events = availability(config, sites, day)
                effects[lot.material_id].update(events)
                if factor == ONE:
                    inbound[lot.material_id] += lot.quantity
                    lot_received.add(lot.id)
                else:
                    actions.append(
                        {
                            "day": day,
                            "lot_id": lot.id,
                            "status": "held",
                            "event_ids": events,
                        }
                    )
        for material in materials:
            stock[material] += (
                regular[material] + inbound[material] + additional[material]
            )
        for order in orders:
            if day >= order.start_day:
                released[order.id] += min(
                    order.daily_demand, order.quantity - released[order.id]
                )
            if released[order.id] - produced[order.id] > order.daily_capacity:
                capacity_days[order.id].append(day)
            target = min(order.daily_capacity, released[order.id] - produced[order.id])
            feasible = min(
                [
                    target,
                    *[int(stock[m] // qty) for m, qty in bom[order.product_id].items()],
                ]
            )
            if feasible < target:
                for material, qty in bom[order.product_id].items():
                    if stock[material] < target * qty:
                        blocked_days[order.id].setdefault(material, []).append(day)
            for material, qty in bom[order.product_id].items():
                used = qty * feasible
                stock[material] -= used
                consumed[material] += used
            produced[order.id] += feasible
            if produced[order.id] == order.quantity and completed[order.id] is None:
                completed[order.id] = day
            if day == order.due_day:
                on_due[order.id] = produced[order.id]
        for material in materials:
            backlog = sum(
                (
                    Decimal(released[o.id] - produced[o.id])
                    * bom[o.product_id].get(material, ZERO)
                    for o in orders
                ),
                ZERO,
            )
            shortage = max(ZERO, backlog - stock[material])
            material_rows[material].append(
                {
                    "day": day,
                    "date": (config.as_of.date() + timedelta(days=day)).isoformat(),
                    "opening_stock": number(opening[material]),
                    "regular_receipts": number(regular[material]),
                    "inbound_receipts": number(inbound[material]),
                    "measure_receipts": number(additional[material]),
                    "consumption": number(consumed[material]),
                    "closing_stock": number(stock[material]),
                    "backlog_material_need": number(backlog),
                    "shortage_units": number(shortage),
                    "constraint_event_ids": sorted(effects[material]),
                }
            )
    outcomes = []
    for order in orders:
        due_observed = order.due_day < config.horizon_days
        late = due_observed and on_due[order.id] < order.quantity
        evidences = []
        for material, days in blocked_days[order.id].items():
            related = set()
            for row in material_rows[material]:
                related.update(row["constraint_event_ids"])
            evidences.append(
                {
                    "material_id": material,
                    "material_name": materials[material].name,
                    "blocked_days": days,
                    "event_ids": sorted(related),
                    "units_per_product": number(bom[order.product_id][material]),
                    "bom_paths": evidence_paths(config, order.product_id, material),
                    "supply_paths": [
                        {
                            "supply_id": supply.id,
                            "source_site_id": supply.source_site_id,
                            "via_site_ids": supply.via_site_ids,
                            "material_id": material,
                        }
                        for supply in config.supplies
                        if supply.material_id == material
                    ],
                    "path_limit": 32,
                    "order_id": order.id,
                }
            )
        done = completed[order.id]
        outcomes.append(
            {
                **order.model_dump(mode="json"),
                "produced_quantity": produced[order.id],
                "released_quantity": released[order.id],
                "completed_day": done,
                "due_observed": due_observed,
                "censored": not due_observed and done is None and order.quantity > 0,
                "delayed": late,
                "days_late": max(0, done - order.due_day) if done is not None else None,
                "delay_lower_bound_days": (
                    max(0, config.horizon_days - 1 - order.due_day)
                    if late and done is None
                    else 0
                ),
                "evidence": evidences,
                "capacity_limited_days": capacity_days[order.id],
                "delay_interval_days": (
                    [max(0, done - order.due_day), max(0, done - order.due_day)]
                    if done is not None
                    else [max(0, config.horizon_days - 1 - order.due_day), None]
                ),
            }
        )
    summaries = []
    for material in config.materials:
        rows = material_rows[material.id]
        planned = [
            sum(
                (
                    Decimal(
                        min(
                            o.daily_demand,
                            max(
                                0,
                                o.quantity - max(0, day - o.start_day) * o.daily_demand,
                            ),
                        )
                    )
                    * bom[o.product_id].get(material.id, ZERO)
                    for o in orders
                    if day >= o.start_day
                ),
                ZERO,
            )
            for day in range(config.horizon_days)
        ]
        demand = max(planned, default=ZERO)
        summaries.append(
            {
                "id": material.id,
                "name": material.name,
                "unit": material.unit,
                "initial_stock": number(material.initial_stock),
                "peak_planned_daily_need": number(demand),
                "initial_buffer_days": (
                    number((material.initial_stock / demand).quantize(Decimal("0.01")))
                    if demand
                    else None
                ),
                "first_shortage_day": next(
                    (r["day"] for r in rows if Decimal(r["shortage_units"]) > 0), None
                ),
                "peak_shortage_units": number(
                    max(Decimal(r["shortage_units"]) for r in rows)
                ),
                "daily": rows,
            }
        )
    delayed = [o for o in outcomes if o["delayed"]]
    last = max(
        (o["completed_day"] for o in outcomes if o["completed_day"] is not None),
        default=None,
    )
    return {
        "metrics": {
            "delayed_orders": len(delayed),
            "delayed_order_amount_cny": money(
                sum((Decimal(o["amount_cny"]) for o in delayed), ZERO)
            ),
            "incremental_cost_cny": money(
                sum((Decimal(c["amount_cny"]) for c in costs), ZERO)
            ),
            "incomplete_orders": sum(
                o["completed_day"] is None and o["quantity"] > 0 for o in outcomes
            ),
            "censored_orders": sum(o["censored"] for o in outcomes),
            "first_shortage_day": min(
                (
                    m["first_shortage_day"]
                    for m in summaries
                    if m["first_shortage_day"] is not None
                ),
                default=None,
            ),
            "last_completion_day": last,
        },
        "materials": summaries,
        "orders": outcomes,
        "cost_ledger": costs,
        "actions": actions,
        "unreceived_lot_ids": sorted(
            lot.id for lot in config.inbounds if lot.id not in lot_received
        ),
        "measures": [m.model_dump(mode="json") for m in measures],
        "scope": "deterministic synthetic daily planning; no probabilistic interval",
        "uncertainty": {
            "kind": "deterministic",
            "confidence_interval": None,
            "note": "不估计统计置信区间；未完成订单只给已观测延误下界，区间上界未知。",
        },
    }


def run_simulation(user: UserContext, request: SimulationRequest):
    if not user.is_member:
        raise PermissionError("enterprise membership required")
    config = build_config(request)
    canonical_request = request.model_dump(mode="json")
    canonical_request["at_time"] = config.as_of.isoformat()
    snapshot = {
        "engine_version": ENGINE_VERSION,
        "tenant_id": str(user.tenant_id),
        "user_id": str(user.user_id),
        "config": config.model_dump(mode="json"),
        "request": canonical_request,
        "measures": [m.model_dump(mode="json") for m in request.measures],
    }
    result = simulate(config, request.measures)
    return {
        "run_id": digest(snapshot),
        "tenant_id": str(user.tenant_id),
        "source_type": "synthetic",
        "engine_version": ENGINE_VERSION,
        "input_snapshot": snapshot,
        "result": result,
        "assumptions": config.assumptions,
    }


def compare_simulations(user: UserContext, request: ComparisonRequest):
    baseline = run_simulation(user, request.simulation)
    plans = []
    for plan in request.plans:
        proposed = run_simulation(
            user, request.simulation.model_copy(update={"measures": plan.measures})
        )
        a, b = baseline["result"]["metrics"], proposed["result"]["metrics"]
        plans.append(
            {
                "id": plan.id,
                "name": plan.name,
                "run": proposed,
                "delta": {
                    "delayed_orders_reduced": a["delayed_orders"] - b["delayed_orders"],
                    "delayed_order_amount_reduced_cny": money(
                        Decimal(a["delayed_order_amount_cny"])
                        - Decimal(b["delayed_order_amount_cny"])
                    ),
                    "incremental_cost_cny": b["incremental_cost_cny"],
                },
            }
        )
    comparison_id = digest(
        {
            "baseline": baseline["run_id"],
            "plans": [(p["id"], p["name"], p["run"]["run_id"]) for p in plans],
        }
    )
    overview = business_overview(user, request.simulation.scenario_id)
    config = SimulationConfig.model_validate(baseline["input_snapshot"]["config"])
    # This is a separate topology-only exposure, derived from lane -> material -> BOM -> order.
    active_sites = {s for e in config.events for s in e.site_ids}
    touched = {
        s.material_id
        for s in config.supplies
        if active_sites.intersection([s.source_site_id, *s.via_site_ids])
    }
    bom = expand_bom(config)
    topology_orders = [
        o
        for o in config.orders
        if touched.intersection(bom[o.product_id]) and o.quantity > 0
    ]
    return {
        "comparison_id": comparison_id,
        "tenant_id": str(user.tenant_id),
        "source_type": "synthetic",
        "engine_version": ENGINE_VERSION,
        "baseline": baseline,
        "plans": plans,
        "exposure_context": {
            "p1_rule_exposure_latest_cny": overview["metrics"]["exposure_amount_cny"],
            "topology_order_amount_cny": money(
                sum((o.amount_cny for o in topology_orders), ZERO)
            ),
            "topology_order_ids": [o.id for o in topology_orders],
            "note": "P1 为最新演示时点的规则敞口；拓扑暴露不考虑库存。约束仿真按当前输入计算延期，三者口径不同。",
        },
        "assumptions": config.assumptions,
    }
