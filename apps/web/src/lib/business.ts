import { useNetworkFilters } from "./network";
import { create } from "zustand";
import { apiClient } from "./api";

export interface Scenario {
  id: string;
  name: string;
  description: string;
  decision_question: string;
}
export interface BusinessOrder {
  id: string;
  customer: string;
  product_name: string;
  supplier_name: string;
  amount_cny: string;
  promised_at: string;
  severity: "medium" | "high" | "critical";
  action_status: "open" | "in_progress" | "resolved";
  risk_event_ids: string[];
}
export interface BusinessEvent {
  id: string;
  name: string;
  kind: string;
  severity: string;
  description: string;
  detected_at: string;
  affected_order_ids: string[];
}
export interface BusinessOverview {
  tenant_id: string;
  workspace_name: string;
  policy_version: string;
  provenance: {
    label: string;
    as_of: string;
    dataset_version: string;
    notice: string;
  };
  scenario: Scenario;
  scenarios: Scenario[];
  metrics: {
    exposure_amount_cny: string;
    at_risk_orders: number;
    pending_high_risk_orders: number;
    active_risk_events: number;
    critical_materials: number;
  };
  definitions: Record<string, string>;
  orders: BusinessOrder[];
  risk_events: BusinessEvent[];
  network_summary: {
    suppliers: number;
    sites: number;
    orders: number;
    shipments: number;
  };
}
export const useBusinessScenario = create<{
  scenarioId: string;
  atTime: string | null;
  setAtTime: (value: string | null) => void;
  selectScenario: (id: string) => void;
}>((set) => ({
  scenarioId: "port-congestion",
  atTime: null,
  setAtTime: (atTime) => set({ atTime }),
  selectScenario: (scenarioId) => {
    useNetworkFilters.getState().reset();
    set({ scenarioId, atTime: null });
  },
}));
export async function getBusinessOverview(
  scenarioId: string,
): Promise<BusinessOverview> {
  const { data } = await apiClient.get<BusinessOverview>("/business/overview", {
    params: { scenario_id: scenarioId },
  });
  return data;
}
export function moneyCny(amount: string | number) {
  return new Intl.NumberFormat("zh-CN", {
    style: "currency",
    currency: "CNY",
    maximumFractionDigits: 2,
  }).format(Number(amount));
}
export function businessDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}
export const riskLabels: Record<string, string> = {
  critical: "严重",
  high: "高风险",
  medium: "关注",
};
export const actionLabels: Record<string, string> = {
  open: "待处理",
  in_progress: "处理中",
  resolved: "处置完成",
};
