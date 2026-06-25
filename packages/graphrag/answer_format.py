"""Graph answer formatting helpers."""

from __future__ import annotations

from packages.graphrag.graph_context import GraphPath, GraphRetrievalResult


def build_graph_answer(result: GraphRetrievalResult) -> str:
    if not result.graph_paths:
        return "根据供应链图谱，未找到符合条件的影响路径。"

    entity = result.matched_entities[0]["code"] if result.matched_entities else "目标实体"
    lines = [f"根据供应链图谱，{entity} 的相关影响路径如下：", ""]
    for index, path in enumerate(result.graph_paths, start=1):
        lines.append(f"{index}. {path.path_text}")

    lines.extend(["", "受影响范围摘要："])
    if result.affected_materials:
        lines.append(f"- 物料：{', '.join(result.affected_materials)}")
    if result.affected_products:
        lines.append(f"- 产品：{', '.join(result.affected_products)}")
    if result.affected_orders:
        lines.append(f"- 订单：{', '.join(result.affected_orders)}")
    if result.affected_customers:
        lines.append(f"- 客户：{', '.join(result.affected_customers)}")

    lines.extend(["", "风险说明：", "- 以上路径来自 Neo4j 供应链知识图谱的结构化关联，不包含合同金额或付款条款。"])
    lines.extend(["", "图谱证据来源："])
    for path in result.graph_paths:
        lines.append(f"* [graph:{path.template_id}#path:{path.path_index}]")
    return "\n".join(lines)


def append_graph_paths_to_answer(answer: str, paths: list[GraphPath]) -> str:
    if not paths:
        return answer
    lines = [answer, "", "供应链路径证据："]
    for path in paths:
        lines.append(f"* [graph:{path.template_id}#path:{path.path_index}] — {path.path_text}")
    return "\n".join(lines)
