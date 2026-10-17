import { apiClient } from "./api";
export interface SimulationMaterial {
  id: string;
  name: string;
  initial_stock: string;
  unit: string;
}
export interface SimulationOption {
  id: string;
  name: string;
  kind: "alternative" | "transfer" | "expedite" | "reroute";
  material_id: string;
  source_site_id: string;
  certified: boolean;
  limit_quantity: string;
  lead_days: number;
  unit_cost_cny: string;
  fixed_cost_cny: string;
  lot_id: string | null;
  description: string;
}
export interface SimulationConfig {
  version: string;
  preset_id: string;
  scenario_id: string;
  as_of: string;
  horizon_days: number;
  materials: SimulationMaterial[];
  supplies: {
    id: string;
    material_id: string;
    source_site_id: string;
    via_site_ids: string[];
    receipt_per_day: string;
    capacity_per_day: string;
  }[];
  inbounds: {
    id: string;
    material_id: string;
    quantity: string;
    arrival_day: number;
    via_site_ids: string[];
  }[];
  events: {
    id: string;
    name: string;
    site_ids: string[];
    start_day: number;
    duration_days: number;
    recovery_days: number;
    capacity_ratio: string;
  }[];
  options: SimulationOption[];
  bom: Record<string, { component_id: string; quantity: string }[]>;
  orders: {
    id: string;
    product_id: string;
    product_name: string;
    quantity: number;
    daily_demand: number;
    daily_capacity: number;
    start_day: number;
    due_day: number;
    amount_cny: string;
  }[];
  assumptions: string[];
}
export interface SimulationTemplate {
  available_events: SimulationConfig["events"];
  config: SimulationConfig;
  default_option_ids: string[];
  target_material_id: string;
  engine_version: string;
}
export interface SimulationMeasure {
  option_id: string;
  quantity: string;
  start_day: number;
  duration_days: number;
}
export interface SimulationPlan {
  id: string;
  name: string;
  measures: SimulationMeasure[];
}
export interface SimulationInput {
  scenario_id: string;
  preset_id: string;
  at_time: string | null;
  horizon_days: number;
  demand_percent: number;
  event_ids: string[];
  event_overrides: {
    event_id: string;
    start_day: number;
    duration_days: number;
    recovery_days: number;
    capacity_ratio: string;
  }[];
  material_overrides: { material_id: string; initial_stock: string }[];
  supply_overrides: { supply_id: string; receipt_per_day: string }[];
  inbound_overrides: { lot_id: string; arrival_day: number }[];
}
export interface SimulationDay {
  day: number;
  date: string;
  opening_stock: string;
  regular_receipts: string;
  inbound_receipts: string;
  measure_receipts: string;
  consumption: string;
  closing_stock: string;
  backlog_material_need: string;
  shortage_units: string;
  constraint_event_ids: string[];
}
export interface MaterialResult {
  id: string;
  name: string;
  unit: string;
  initial_stock: string;
  initial_buffer_days: string | null;
  peak_planned_daily_need: string;
  first_shortage_day: number | null;
  peak_shortage_units: string;
  daily: SimulationDay[];
}
export interface OrderEvidence {
  supply_paths: {
    supply_id: string;
    source_site_id: string;
    via_site_ids: string[];
    material_id: string;
  }[];
  material_id: string;
  material_name: string;
  blocked_days: number[];
  event_ids: string[];
  units_per_product: string;
  bom_paths: { nodes: string[]; units_per_product: string }[];
}
export interface OrderResult {
  censored: boolean;
  capacity_limited_days: number[];
  id: string;
  product_id: string;
  product_name: string;
  quantity: number;
  produced_quantity: number;
  amount_cny: string;
  completed_day: number | null;
  due_day: number;
  due_observed: boolean;
  delayed: boolean;
  days_late: number | null;
  delay_lower_bound_days: number;
  evidence: OrderEvidence[];
}
export interface SimulationRun {
  run_id: string;
  engine_version: string;
  input_snapshot: { config: SimulationConfig };
  result: {
    metrics: {
      delayed_orders: number;
      delayed_order_amount_cny: string;
      incremental_cost_cny: string;
      first_shortage_day: number | null;
      incomplete_orders: number;
      censored_orders: number;
    };
    materials: MaterialResult[];
    orders: OrderResult[];
    cost_ledger: {
      day: number;
      option_id: string;
      quantity: string;
      amount_cny: string;
    }[];
    actions: {
      day: number;
      option_id?: string;
      lot_id?: string;
      status: string;
      event_ids?: string[];
      arrival_day?: number;
      quantity?: string;
    }[];
  };
  assumptions: string[];
}
export interface SimulationComparison {
  comparison_id: string;
  engine_version: string;
  source_type: string;
  baseline: SimulationRun;
  plans: {
    id: string;
    name: string;
    run: SimulationRun;
    delta: {
      delayed_orders_reduced: number;
      delayed_order_amount_reduced_cny: string;
      incremental_cost_cny: string;
    };
  }[];
  exposure_context: {
    p1_rule_exposure_latest_cny: string;
    topology_order_amount_cny: string;
    note: string;
  };
  assumptions: string[];
}
export const simulationKind = {
  alternative: "替代采购",
  transfer: "库存调拨",
  expedite: "加急运输",
  reroute: "在途改道",
};
export const simulationDay = (day: number | null) =>
  day === null ? "未出现" : `D${day + 1}`;
export const defaultMeasure = (
  option: SimulationOption,
  hand: boolean,
): SimulationMeasure => ({
  option_id: option.id,
  quantity:
    option.kind === "alternative"
      ? String(Math.min(hand ? 20 : 60, Number(option.limit_quantity)))
      : option.kind === "transfer"
        ? String(Math.min(80, Number(option.limit_quantity)))
        : "1",
  start_day: 0,
  duration_days: option.kind === "alternative" ? 7 : 1,
});
export async function getSimulationTemplate(params: {
  scenario_id: string;
  preset_id: string;
  at_time: string | null;
  event_id: string | null;
}): Promise<SimulationTemplate> {
  return (await apiClient.get("/simulation/templates", { params })).data;
}
export async function compareSimulation(payload: {
  simulation: SimulationInput;
  plans: SimulationPlan[];
}): Promise<SimulationComparison> {
  return (await apiClient.post("/simulation/comparison", payload)).data;
}
export function simulationError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })
    ?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((d) => `${d.loc?.slice(1).join(".")}: ${d.msg}`)
      .join("；");
  return "计算服务暂不可用，请检查输入或重试。";
}
