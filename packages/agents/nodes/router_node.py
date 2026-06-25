"""Rule-based workflow router."""

from __future__ import annotations

import re

from packages.agents.state import AgentState
from packages.graphrag.graph_schema import QUERY_TYPES

from packages.memory.memory_policy import is_memory_followup_query

MEMORY_KEYWORDS = (
    "上次",
    "之前",
    "上一轮",
    "那个供应商",
    "为什么风险",
    "历史分析",
    "还记得",
)

GRAPH_KEYWORDS = (
    "影响哪些产品",
    "影响哪些订单",
    "依赖哪些供应商",
    "替代供应商",
    "供应链路径",
    "多跳",
    "客户订单依赖",
    "交付延迟",
    "质量问题",
    "图谱",
)

RAG_KEYWORDS = (
    "合同",
    "条款",
    "付款",
    "违约",
    "政策",
    "质检报告内容",
    "pricing",
    "payment",
)

TOOL_INTENT_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("query_supplier_profile", ("供应商档案", "supplier profile", "查询供应商档案", "供应商基本信息")),
    ("query_supplier_risk_events", ("风险事件", "risk events", "供应商风险")),
    ("query_supplier_delivery_history", ("交付历史", "delivery history", "供货历史")),
    ("query_supplier_contract_summary", ("合同摘要", "contract summary", "合同概要")),
    ("query_delivery_status", ("物流状态", "delivery status", "查询物流状态", "发货状态", "订单状态")),
    ("query_delay_events", ("延迟事件", "delay events", "物流延迟")),
    ("query_route_info", ("路线信息", "route info", "运输路线")),
    ("export_risk_report", ("导出风险报告", "export risk report", "导出报告")),
    ("export_benchmark_results", ("导出benchmark", "export benchmark", "导出评测")),
]

ORDER_PATTERN = re.compile(r"\b(PO-\d{4}-\d{4})\b", re.IGNORECASE)

ENTITY_PATTERNS = {
    "supplier": re.compile(r"\b(SUP-\d{3}|S\d{3})\b", re.IGNORECASE),
    "product": re.compile(r"\b(P\d{3})\b", re.IGNORECASE),
    "customer": re.compile(r"\b(C\d{3})\b", re.IGNORECASE),
    "quality": re.compile(r"\b(QI-\d{3})\b", re.IGNORECASE),
}


def _normalize_supplier_code(code: str) -> str:
    upper = code.upper()
    if upper.startswith("S") and not upper.startswith("SUP-"):
        digits = upper[1:]
        if digits.isdigit():
            return f"SUP-{digits.zfill(3)}"
    return upper


def infer_query_type(query: str) -> str:
    lowered = query.lower()
    if any(k in query for k in ("替代供应商", "alternative")):
        return "supplier_alternatives"
    if any(k in query for k in ("交付延迟", "delay", "物流延迟")):
        return "delivery_delay_impact"
    if any(k in query for k in ("质量问题", "quality issue", "质检")):
        return "quality_issue_trace"
    if any(k in query for k in ("客户", "customer")) and any(k in query for k in ("依赖", "订单")):
        return "customer_order_dependency"
    if any(k in query for k in ("产品", "product")) and "依赖" in query:
        return "product_dependency"
    if any(k in query for k in ("供应商", "supplier", "延迟", "影响")):
        return "supplier_impact"
    return "supplier_impact"


def extract_entity_code(query: str, query_type: str) -> str | None:
    if query_type == "product_dependency":
        match = ENTITY_PATTERNS["product"].search(query)
        return match.group(1).upper() if match else None
    if query_type == "customer_order_dependency":
        match = ENTITY_PATTERNS["customer"].search(query)
        return match.group(1).upper() if match else None
    if query_type == "quality_issue_trace":
        match = ENTITY_PATTERNS["quality"].search(query)
        return match.group(1).upper() if match else None
    match = ENTITY_PATTERNS["supplier"].search(query)
    if match:
        return _normalize_supplier_code(match.group(1))
    return None


def detect_tool_request(query: str) -> tuple[str | None, dict[str, str]]:
    lowered = query.lower()
    for tool_name, keywords in TOOL_INTENT_PATTERNS:
        if any(keyword.lower() in lowered for keyword in keywords):
            tool_input: dict[str, str] = {}
            supplier_match = ENTITY_PATTERNS["supplier"].search(query)
            if supplier_match:
                tool_input["supplier_code"] = _normalize_supplier_code(supplier_match.group(1))
            order_match = ORDER_PATTERN.search(query)
            if order_match:
                tool_input["order_no"] = order_match.group(1).upper()
            return tool_name, tool_input
    return None, {}


def decide_route(query: str, *, use_memory: bool = True) -> tuple[str, str, str | None]:
    graph_hit = any(keyword in query for keyword in GRAPH_KEYWORDS) or bool(
        ENTITY_PATTERNS["supplier"].search(query)
        or ENTITY_PATTERNS["product"].search(query)
        or ENTITY_PATTERNS["customer"].search(query)
    )
    rag_hit = any(keyword in query for keyword in RAG_KEYWORDS)
    memory_hit = use_memory and (
        is_memory_followup_query(query) or any(keyword in query for keyword in MEMORY_KEYWORDS)
    )

    if memory_hit and not graph_hit and not rag_hit:
        route_mode = "memory"
    elif graph_hit and rag_hit:
        route_mode = "hybrid"
    elif memory_hit and (graph_hit or rag_hit):
        route_mode = "memory_rag" if rag_hit else "graphrag"
    elif graph_hit:
        route_mode = "graphrag"
    else:
        route_mode = "rag"

    query_type = infer_query_type(query)
    if query_type not in QUERY_TYPES:
        query_type = "supplier_impact"
    entity_code = extract_entity_code(query, query_type)
    return route_mode, query_type, entity_code


async def router_node(state: AgentState) -> AgentState:
    if state.get("permission_decision") and not state["permission_decision"].allowed:
        return {"route_mode": "blocked", "nodes_executed": ["router_skipped"]}

    tool_name, tool_input = detect_tool_request(state["query"])
    if tool_name:
        return {
            "route_mode": "tool",
            "tool_name": tool_name,
            "tool_input": tool_input,
            "nodes_executed": ["router"],
        }

    route_mode, query_type, entity_code = decide_route(
        state["query"], use_memory=state.get("use_memory", True)
    )
    return {
        "route_mode": route_mode,
        "tool_name": None,
        "tool_input": {},
        "graph_query_type": query_type,
        "graph_entity_code": entity_code,
        "nodes_executed": ["router"],
    }
