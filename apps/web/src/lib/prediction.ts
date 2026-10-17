import { apiClient } from "./api";
export interface Metric {
  count: number;
  positive_rate: number;
  average_precision: number | null;
  roc_auc: number | null;
  brier?: number;
  ece?: number;
  precision?: number;
  recall?: number;
  f1?: number;
  threshold?: number;
  confusion?: { tp: number; fp: number; tn: number; fn: number };
  ranking: Record<
    string,
    {
      k: number;
      recall: number | null;
      precision: number;
      late_quoted_amount_capture: number | null;
    }
  >;
  calibration?: {
    lower: number;
    count: number;
    mean_probability: number | null;
    observed_rate: number | null;
  }[];
}
export interface PredictionReport {
  tenant_id: string;
  run_id: string;
  model_version: string;
  protocol_version: string;
  protocol_sha256: string;
  source_sha256: string;
  domain: string;
  source_type: string;
  source: {
    source: string;
    doi: string;
    license: string;
    contributors: string[];
  };
  audit: {
    raw_items: number;
    raw_orders: number;
    excluded_cancel_fraud_orders: number;
    excluded_other_invalid_orders: number;
    same_order_overlap: number;
    split_counts: Record<string, number>;
  };
  splits: Record<
    string,
    {
      count: number;
      positive_rate: number;
      min_time: string;
      max_time: string;
      ids_sha256: string;
    }
  >;
  selection: { name: string; validation_ap: number; threshold: number };
  candidates: { name: string; validation_ap: number; threshold: number }[];
  models: Record<string, { test: Metric }>;
  uncertainty: {
    method: string;
    blocks: number;
    resamples: number;
    intervals: Record<string, { low: number; high: number }>;
  };
  subgroups: Record<string, Record<string, Metric>>;
  ablation: Record<string, string>;
  failure_cases: {
    case_id: string;
    kind: string;
    probability: number;
    label: number;
    mode: string;
    month: number;
  }[];
  limitations: string[];
  elapsed_seconds: number;
}
export interface HistoricalCase {
  case_id: string;
  placed: string;
  label: number;
  probability: number;
  unknown_categories: string[];
  features: Record<string, string | number>;
}
export interface PredictionResult {
  case_id: string;
  probability: number;
  threshold: number;
  predicted_late: boolean;
  model_version: string;
  domain: string;
  unknown_categories: string[];
  observed_label_for_review: number;
  features: Record<string, string | number>;
}
export const getPredictionReport = async () =>
  (await apiClient.get<PredictionReport>("/prediction/report")).data;
export const getPredictionCases = async () =>
  (await apiClient.get<{ items: HistoricalCase[] }>("/prediction/cases")).data
    .items;
export const predictHistorical = async (case_id: string) =>
  (
    await apiClient.post<PredictionResult>("/prediction/predict", {
      case_id,
      domain: "dataco-retail-historical",
    })
  ).data;
export interface Contracts {
  status: string;
  dataset_version: string;
  scorer_version: string;
  dataset_sha256: string;
  evaluated_contracts: number;
  gold_only_cases: number;
  live_retrieval_status: string;
  rows: { id: string; kind: string; status: string }[];
}
export const getContracts = async () =>
  (await apiClient.get<Contracts>("/prediction/evaluation-contracts")).data;
export async function downloadPrediction(name: string) {
  const { data } = await apiClient.get(`/prediction/artifacts/${name}`, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const modelLabel = (name: string) =>
  name === "global_train_rate"
    ? "全局历史率"
    : name === "mature_product_history"
      ? "产品历史率"
      : name === "fixed_shipping_rule"
        ? "固定发运规则"
        : name === "quoted_amount_ranking"
          ? "按订单金额排序"
          : name.startsWith("logistic")
            ? "逻辑回归 " + name.split("C")[1]
            : name
                .replace("lightgbm_base_", "LightGBM 基础 / ")
                .replace("lightgbm_history_", "LightGBM +历史 / ")
                .replace("lightgbm_graph_", "LightGBM +图结构 / ");
