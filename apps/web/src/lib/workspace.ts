import { apiClient } from "./api";
import { useRef } from "react";
import { useMutation } from "@tanstack/react-query";
export interface Entity {
  id: string;
  kind: string;
  code: string;
  name: string;
  source_type: string;
  source_ref: string;
  import_batch_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}
export interface Task {
  id: string;
  record_id: string;
  title: string;
  state: string;
  version: number;
  assignee_id: string | null;
  due_at: string;
  measures: string;
  actual_cost_cny: string;
  result: string;
  created_at: string;
}
export interface Batch {
  id: string;
  kind: string;
  filename: string;
  state: string;
  source_type: string;
  errors: { row: number; field: string; code: string; message: string }[];
  preview?: { row: number; data: Record<string, unknown> }[];
  row_count?: number;
  valid_rows?: number;
  source_sha256: string;
}
export interface Report {
  id: string;
  kind: string;
  format: string;
  filename: string;
  sha256: string;
  summary: Record<string, unknown>;
  expires_at: string;
  created_at: string;
  download_url?: string;
}
export interface Subscription {
  id: string;
  name: string;
  topics: string[];
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export const kinds: Record<string, string> = {
  site: "站点",
  order: "订单",
  shipment: "运输批次",
  event: "风险事件",
  prediction: "历史预测归档",
  simulation: "模拟快照归档",
};
export const sources: Record<string, string> = {
  synthetic: "模拟数据",
  enterprise_uploaded: "企业上传 · 未经外部核验",
  public_historical: "公开历史验证",
};
export const states: Record<string, string> = {
  open: "待认领",
  in_progress: "处理中",
  pending_verification: "待验证",
  completed: "已完成",
  cancelled: "已取消",
};
export async function getWorkspace<T>(path: string) {
  return (await apiClient.get<T>("/workspace" + path)).data;
}
export async function sendWorkspace<T>(
  path: string,
  body: unknown,
  key: string,
  method = "post",
) {
  return (
    await apiClient.request<T>({
      url: "/workspace" + path,
      method,
      data: body,
      headers: {
        "Idempotency-Key": key,
        ...(body instanceof FormData
          ? { "Content-Type": "multipart/form-data" }
          : {}),
      },
    })
  ).data;
}
/** Keep the key across a failed response. A new body means a new user intent. */
export function useCommand<T, V>(fn: (value: V, key: string) => Promise<T>) {
  const keys = useRef(new Map<string, string>());
  return useMutation({
    mutationFn: (value: V) => {
      const f = JSON.stringify(value);
      let key = keys.current.get(f);
      if (!key) {
        key = crypto.randomUUID();
        keys.current.set(f, key);
      }
      return fn(value, key);
    },
  });
}
export function workspaceError(e: unknown) {
  const error = e as {
    response?: {
      data?: { error?: { code?: string; message?: string }; detail?: unknown };
    };
  };
  const code = error.response?.data?.error?.code;
  const labels: Record<string, string> = {
    version_conflict: "任务已被更新，请重新加载后核对再操作。",
    idempotency_conflict: "请求内容与先前操作不一致，请重新核对。",
    preview_invalid: "预检包含错误，未导入任何业务记录。",
    reference_not_found: "当前企业中找不到引用对象，请先导入站点、订单。",
    report_expired: "报告已过期，请重新生成。",
    invalid_assignee: "责任人必须是本企业有效成员。",
    invalid_transition: "该状态不允许此操作，或缺少取消原因。",
    missing_result: "请填写结果或复核说明。",
    missing_actual_cost: "请填写执行费用；没有费用也应明确填0。",
    missing_execution_details: "请先分配责任人并填写措施。",
    existing_code_conflict: "该编号已有不同内容；导入不会覆盖现有数据。",
    not_found: "当前企业中找不到该记录。",
    storage_unavailable: "存储暂不可用，请稍后使用同一请求重试。",
  };
  return (
    (code && labels[code]) ||
    error.response?.data?.error?.message ||
    "操作未成功，请检查文件、必填项或服务状态后重试。"
  );
}
export async function downloadWorkspace(path: string, name: string) {
  const { data } = await apiClient.get("/workspace" + path, {
    responseType: "blob",
  });
  const url = URL.createObjectURL(data);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
