import axios, { AxiosError, AxiosInstance } from "axios";

/** Empty = use Next.js dev proxy (same origin, no CORS). Set full URL to call API directly. */
const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

function apiBaseUrl(path: string): string {
  if (API_BASE) {
    return `${API_BASE.replace(/\/$/, "")}${path}`;
  }
  return path;
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: apiBaseUrl("/api/v1"),
  headers: { "Content-Type": "application/json" },
  timeout: 180000,
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("sg_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

apiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("sg_token");
      localStorage.removeItem("sg_user");
      if (!window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  },
);

// --- Types ---
export interface UserInfo {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  department: string;
  tenant_id: string;
  supplier_id: string | null;
}

export interface LoginResponse {
  access_token: string;
  user: UserInfo;
}

export interface PermissionsResponse {
  roles: string[];
  max_security_rank: number;
  can_access_admin: boolean;
  can_upload_document: boolean;
  can_run_benchmark: boolean;
}

export interface GraphPathItem {
  path_index: number;
  path_text: string;
  nodes: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  template_id: string;
  graph_path_ref: string | null;
}

export interface GraphRAGResponse {
  query: string;
  query_type: string;
  matched_entities: Record<string, unknown>[];
  graph_paths: GraphPathItem[];
  affected_suppliers: string[];
  affected_materials: string[];
  affected_products: string[];
  affected_orders: string[];
  affected_customers: string[];
  cypher_template: string;
  trace_id: string;
  latency_ms: number;
  result_count: number;
  permission_decision: string;
}

export interface RAGResponse {
  query: string;
  answer: string;
  citations: {
    document_id: string;
    chunk_id: string | null;
    chunk_index: number;
    title: string;
    score: number;
    snippet: string;
  }[];
  trace_id: string;
  status: string;
  retrieval: {
    top_k: number;
    result_count: number;
    filter_applied: Record<string, unknown>;
    latency_ms?: number;
  };
}

export interface ChatResponse {
  answer: string;
  citations: RAGResponse["citations"];
  trace_id: string;
  agent_run_id: string;
  nodes_executed: string[];
  token_usage: Record<string, unknown>;
  status: string;
  route_mode: string | null;
  memory_used: Record<string, unknown>[];
  memory_written: Record<string, unknown>[];
  context_budget: { max_tokens: number; used_tokens: number } | null;
}

export interface TraceDetail {
  trace_id: string;
  request: Record<string, unknown>;
  agent_run: Record<string, unknown> | null;
  retrieval_logs: Record<string, unknown>[];
  graph_retrieval_logs: Record<string, unknown>[];
  audit_logs: Record<string, unknown>[];
  memory_events: Record<string, unknown>[];
  tool_calls: Record<string, unknown>[];
  benchmark_results: Record<string, unknown>[];
  benchmark_runs: Record<string, unknown>[];
  node_spans: Record<string, unknown>[];
  timeline: {
    type: string;
    name: string;
    latency_ms?: number;
    status?: string;
  }[];
  summary: Record<string, unknown>;
}

export interface ToolDefinition {
  name: string;
  description: string;
  server: string;
  input_schema: Record<string, unknown>;
  high_risk: boolean;
}

export interface ToolCallResponse {
  tool_name: string;
  status: string;
  result: Record<string, unknown>;
  trace_id: string;
  tool_call_id: string | null;
  permission_decision: string;
  approval_required: boolean;
  latency_ms: number;
}

export interface BenchmarkRunItem {
  id: string;
  name: string;
  mode: string;
  status: string;
  summary: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
}

export interface BenchmarkRunResponse {
  benchmark_run_id: string | null;
  trace_id: string | null;
  status: string;
  summary: Record<string, unknown>;
}

export interface BenchmarkRunRequest {
  name: string;
  mode: "secure_rag" | "graphrag" | "memory" | "permission" | "all";
  limit?: number;
  dry_run?: boolean;
  config?: {
    top_k?: number;
    chunk_size?: number;
    permission_filter?: boolean;
    memory?: boolean;
  };
}

export interface AuditLogItem {
  id: string;
  action: string;
  resource_type: string;
  permission_decision: string;
  reason: string;
  created_at: string;
}

export interface DashboardSummary {
  health: {
    status: string;
    dependencies: Record<string, { status: string; model?: string }>;
  };
  benchmark_snapshot: Record<string, unknown> | null;
  audit_stats: { total: number; denied_count: number };
  capability_status: Record<string, string>;
}

// --- Auth ---
export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>("/auth/login", {
    email,
    password,
  });
  return data;
}

export async function getMe(): Promise<UserInfo> {
  const { data } = await apiClient.get<UserInfo>("/auth/me");
  return data;
}

export async function getPermissions(): Promise<PermissionsResponse> {
  const { data } = await apiClient.get<PermissionsResponse>(
    "/users/me/permissions",
  );
  return data;
}

// --- Health ---
export async function getHealth(): Promise<{ status: string }> {
  const { data } = await axios.get(apiBaseUrl("/health"));
  return data;
}

export async function getHealthDependencies(): Promise<{
  status: string;
  dependencies: Record<
    string,
    { status: string; model?: string; provider?: string }
  >;
}> {
  const { data } = await axios.get(apiBaseUrl("/health/dependencies"));
  return data;
}

// --- Dashboard ---
export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>("/dashboard/summary");
  return data;
}

// --- RAG ---
export async function ragQuery(body: {
  query: string;
  top_k?: number;
  doc_type?: string | null;
  chunk_size?: number;
}): Promise<RAGResponse> {
  const { data } = await apiClient.post<RAGResponse>("/rag/query", body);
  return data;
}

// --- GraphRAG ---
export async function graphragQuery(body: {
  query: string;
  query_type: string;
  entity_code?: string | null;
  top_k?: number;
}): Promise<GraphRAGResponse> {
  const { data } = await apiClient.post<GraphRAGResponse>(
    "/graphrag/query",
    body,
  );
  return data;
}

// --- Chat ---
export async function chatQuery(body: {
  query: string;
  session_id?: string;
  top_k?: number;
  use_memory?: boolean;
}): Promise<ChatResponse> {
  const { data } = await apiClient.post<ChatResponse>("/chat", body);
  return data;
}

// --- Memory ---
export async function getSessionMemory(sessionId: string) {
  const { data } = await apiClient.get(`/memory/session/${sessionId}`);
  return data;
}

export async function listLongTermMemory() {
  const { data } = await apiClient.get("/memory/long-term");
  return data;
}

export async function createLongTermMemory(body: {
  content: string;
  memory_type: string;
  importance?: number;
}) {
  const { data } = await apiClient.post("/memory/long-term", body);
  return data;
}

// --- Traces ---
export async function getTrace(traceId: string): Promise<TraceDetail> {
  const { data } = await apiClient.get<TraceDetail>(`/traces/${traceId}`);
  return data;
}

// --- Tools ---
export async function listTools(): Promise<{ tools: ToolDefinition[] }> {
  const { data } = await apiClient.get("/tools");
  return data;
}

export async function callTool(body: {
  tool_name: string;
  tool_input: Record<string, unknown>;
}): Promise<ToolCallResponse> {
  const { data } = await apiClient.post<ToolCallResponse>("/tools/call", body);
  return data;
}

// --- Benchmarks ---
export async function listBenchmarkRuns(
  limit = 20,
): Promise<BenchmarkRunItem[]> {
  const { data } = await apiClient.get<BenchmarkRunItem[]>("/benchmarks/runs", {
    params: { limit },
  });
  return data;
}

export async function getBenchmarkRun(
  runId: string,
): Promise<BenchmarkRunItem> {
  const { data } = await apiClient.get<BenchmarkRunItem>(
    `/benchmarks/runs/${runId}`,
  );
  return data;
}

export async function getBenchmarkResults(runId: string) {
  const { data } = await apiClient.get(`/benchmarks/runs/${runId}/results`);
  return data;
}

export async function runBenchmark(
  body: BenchmarkRunRequest,
): Promise<BenchmarkRunResponse> {
  const { data } = await apiClient.post<BenchmarkRunResponse>(
    "/benchmarks/run",
    body,
    {
      timeout: 60000,
    },
  );
  return data;
}

// --- Audit ---
export async function listAuditLogs(limit = 50, offset = 0) {
  const { data } = await apiClient.get<{
    items: AuditLogItem[];
    total: number;
  }>("/admin/audit-logs", {
    params: { limit, offset },
  });
  return data;
}

// --- Documents ---
export async function uploadDocument(form: FormData) {
  const { data } = await apiClient.post("/documents/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

// --- Supply chain impact (aggregated) ---
export async function runImpactSimulation(body: {
  source_node_type: string;
  source_node_code: string;
  risk_type: string;
  severity: string;
  max_hops?: number;
  include_alternatives?: boolean;
  include_actions?: boolean;
}) {
  const { data } = await apiClient.post("/supply-chain/impact", body);
  return data;
}

export const SEED_USERS = [
  { email: "enterprise@example.com", role: "enterprise", label: "企业用户" },
  { email: "admin@example.com", role: "admin", label: "管理员（开发人员）" },
] as const;

export const DEMO_SCENARIOS = [
  {
    id: "secure-rag",
    title: "Secure RAG 权限演示",
    query: "供应商 SUP-001 的合同付款条款是什么？",
    path: "/rag",
  },
  {
    id: "graphrag",
    title: "GraphRAG 多跳演示",
    query: "供应商 SUP-001 延迟会影响哪些产品、订单和客户？",
    path: "/graphrag",
    query_type: "supplier_impact",
    entity_code: "SUP-001",
  },
  {
    id: "impact",
    title: "供应链风险传播",
    query: "如果 SUP-001 出现严重交付延误，会影响哪些下游节点？",
    path: "/supply-chain",
  },
  {
    id: "alternatives",
    title: "替代供应商",
    query: "SUP-001 不可用时有哪些替代供应商？",
    path: "/graphrag",
    query_type: "supplier_alternatives",
    entity_code: "SUP-001",
  },
  {
    id: "memory",
    title: "记忆追问",
    query: "上次我们为什么认为 SUP-001 风险较高？",
    path: "/agent",
  },
  {
    id: "tool",
    title: "工具权限演示",
    query: "查询供应商 SUP-001 的合同摘要",
    path: "/tools",
    tool_name: "query_supplier_contract_summary",
  },
  {
    id: "supplier-portal",
    title: "供应商门户",
    query: "查看我的订单交付状态",
    path: "/tools",
    tool_name: "query_delivery_status",
  },
] as const;

export const DEFAULT_PASSWORD = "password123";
