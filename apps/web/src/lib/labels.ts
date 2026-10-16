/** Chinese display labels only. API values and diagnostic JSON stay unchanged. */
const LABELS: Record<string, string> = {
  admin: "管理员",
  procurement_manager: "采购经理",
  procurement_staff: "采购专员",
  logistics_manager: "物流经理",
  finance_manager: "财务经理",
  quality_manager: "质量经理",
  executive: "管理层",
  external_supplier: "外部供应商",
  guest: "访客",
  allowed: "允许",
  denied: "拒绝",
  partial: "部分允许",
  approval_required: "待审批",
  ok: "正常",
  degraded: "部分服务异常",
  error: "异常",
  no_data: "暂无数据",
  not_configured: "未配置",
  success: "成功",
  failed: "失败",
  running: "运行中",
  queued: "排队中",
  pending: "待处理",
  completed: "已完成",
  skipped: "已跳过",
  blocked: "已拦截",
  active: "生效中",
  investigating: "调查中",
  monitoring: "监测中",
  recommended: "建议执行",
  optional: "可选操作",
  low: "低",
  medium: "中",
  high: "高",
  critical: "严重",
  delivery_delay: "交付延误",
  quality_failure: "质量异常",
  financial_risk: "财务风险",
  compliance_risk: "合规风险",
  Supplier: "供应商",
  Material: "物料",
  Product: "产品",
  Order: "订单",
  Customer: "客户",
  RiskEvent: "风险事件",
  DeliveryEvent: "交付事件",
  QualityIssue: "质量问题",
  Unknown: "未知类型",
  supplier: "供应商",
  material: "物料",
  product: "产品",
  order: "订单",
  customer: "客户",
  supplier_impact: "供应商影响分析",
  product_dependency: "产品依赖分析",
  supplier_alternatives: "替代供应商分析",
  delivery_delay_impact: "交付延误影响",
  quality_issue_trace: "质量问题追溯",
  customer_order_dependency: "客户订单依赖",
  secure_rag: "Secure RAG",
  graphrag: "GraphRAG",
  rag: "RAG",
  hybrid: "混合检索",
  memory_rag: "记忆增强 RAG",
  all: "全部模式",
  permission: "权限校验",
  router: "路由分发",
  memory: "记忆",
  tool: "工具调用",
  tool_node: "工具调用节点",
  risk_agent: "风险分析 Agent",
  evidence_aggregator: "证据聚合",
  aggregator: "证据聚合",
  report: "报告生成",
  review: "结果审核",
  memory_writer: "记忆写入",
  graph: "图谱查询",
  benchmark: "基准评测",
  tools: "工具调用",
  confidential: "机密文档",
  node: "工作流节点",
  retrieval: "证据检索",
  audit: "权限审计",
  read: "读取记忆",
  write: "写入记忆",
  session: "会话记忆",
  feedback: "用户反馈",
  risk_summary: "风险摘要",
  supplier_preference: "供应商偏好",
  user_preference: "用户偏好",
  decision: "决策记录",
  SUPPLIES: "供应",
  USED_IN: "用于生产",
  ORDERED_IN: "关联订单",
  FOR_CUSTOMER: "交付客户",
  HAS_RISK: "存在风险",
  ALTERNATIVE_TO: "可替代",
  LINK: "关联",
};

export const SECURITY_LEVEL_LABELS: Record<string, string> = {
  public: "公开",
  internal: "内部",
  department: "部门专属",
  confidential: "机密",
  executive: "高管专属",
};

const TOOL_LABELS: Record<string, string> = {
  query_supplier_profile: "查询供应商档案",
  query_supplier_risk_events: "查询供应商风险事件",
  query_supplier_delivery_history: "查询供应商交付历史",
  query_supplier_contract_summary: "查询供应商合同摘要",
  query_delivery_status: "查询交付状态",
  query_delay_events: "查询交付延误事件",
  query_route_info: "查询物流路线",
  export_risk_report: "导出风险报告",
  export_benchmark_results: "导出基准评测结果",
};

const TOOL_DESCRIPTIONS: Record<string, string> = {
  query_supplier_profile: "根据供应商编码或 ID 查询基本档案。",
  query_supplier_risk_events: "查看供应商近期的风险事件。",
  query_supplier_delivery_history: "查看供应商近期的交付订单。",
  query_supplier_contract_summary: "汇总供应商合同文档中的关键内容。",
  query_delivery_status: "根据订单号或供应商编码查询交付状态。",
  query_delay_events: "查看交付延误事件。",
  query_route_info: "查询起点与终点之间的物流路线信息。",
  export_risk_report: "导出风险报告，执行前需要审批。",
  export_benchmark_results: "导出基准评测结果，执行前需要审批。",
};

export function displayLabel(value: string | null | undefined): string {
  if (!value) return "—";
  return Object.prototype.hasOwnProperty.call(LABELS, value) ? LABELS[value] : value;
}

export function securityLevelLabel(value: string): string {
  return Object.prototype.hasOwnProperty.call(SECURITY_LEVEL_LABELS, value)
    ? SECURITY_LEVEL_LABELS[value]
    : value;
}

export function toolLabel(name: string): string {
  return Object.prototype.hasOwnProperty.call(TOOL_LABELS, name) ? TOOL_LABELS[name] : name;
}

export function toolDescription(name: string, fallback: string): string {
  return Object.prototype.hasOwnProperty.call(TOOL_DESCRIPTIONS, name)
    ? TOOL_DESCRIPTIONS[name]
    : fallback;
}

export function actionLabel(action: string): string {
  if (action.startsWith("Check alternative supplier ")) {
    return `评估替代供应商 ${action.slice("Check alternative supplier ".length)}`;
  }
  const actions: Record<string, string> = {
    "Notify procurement manager": "通知采购经理",
    "Query delivery status via MCP": "通过 MCP 查询交付状态",
    "Generate risk report (approval required)": "生成风险报告（需审批）",
  };
  return Object.prototype.hasOwnProperty.call(actions, action) ? actions[action] : action;
}

export function graphPathLabel(path: string): string {
  return path.replace(/\b(Supplier|Material|Product|Order|Customer|RiskEvent|DeliveryEvent|QualityIssue)(?=\s)/g, displayLabel);
}

export function errorLabel(message: string | undefined, fallback = "请求失败，请稍后重试"): string {
  if (!message) return fallback;
  const errors: Record<string, string> = {
    "Invalid email or password": "邮箱或密码错误",
    "User is inactive": "账号已停用，请联系管理员",
    "Network Error": "网络连接失败，请确认后端服务已启动",
    "Failed to fetch": "无法连接服务，请检查网络连接",
  };
  if (Object.prototype.hasOwnProperty.call(errors, message)) return errors[message];
  if (/^timeout of \d+ms exceeded$/.test(message)) return "请求超时，请稍后重试";
  return message.replace(/^Request failed with status code (\d+)$/, "请求失败（HTTP $1）");
}

export const GRAPH_ARIA_LABELS = {
  "controls.ariaLabel": "图谱操作",
  "controls.zoomIn.ariaLabel": "放大",
  "controls.zoomOut.ariaLabel": "缩小",
  "controls.fitView.ariaLabel": "适应画布",
  "controls.interactive.ariaLabel": "切换交互模式",
  "minimap.ariaLabel": "图谱缩略图",
};
