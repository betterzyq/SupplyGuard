#!/usr/bin/env python3
"""Generate SupplyGuard eval dataset (>=100 questions)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUTPUT = ROOT / "data" / "eval" / "supplyguard_eval.jsonl"

SUPPLIER_PATH = [
    "Supplier:SUP-001",
    "Material:M001",
    "Product:P001",
    "Order:PO-2024-0001",
    "Customer:C001",
]


def _row(**kwargs) -> dict:
    return kwargs


def build_questions() -> list[dict]:
    items: list[dict] = []
    idx = 1

    def add(**kwargs) -> None:
        nonlocal idx
        kwargs.setdefault("id", f"q_{idx:03d}")
        items.append(kwargs)
        idx += 1

    # 1. Single document QA
    single_docs = [
        ("public-policy", "Public Supply Policy 的主要内容是什么？", "procurement_manager"),
        ("internal-procurement-guide", "内部采购指南对供应商准入有哪些要求？", "procurement_manager"),
        ("department-logistics-report", "物流延迟分析报告提到了哪些延迟原因？", "logistics_manager"),
        ("quality-report", "质量检验报告中有哪些缺陷类型？", "quality_manager"),
        ("executive-summary", "高管风险摘要的核心结论是什么？", "executive"),
        ("supplier-portal-sup001", "SUP-001 供应商门户通知中的交付状态如何？", "external_supplier"),
        ("finance-pricing-terms", "财务定价条款中的付款周期是什么？", "finance_manager"),
        ("confidential-supplier-contract", "机密供应商框架合同的关键条款有哪些？", "procurement_manager"),
    ]
    for slug, question, role in single_docs:
        add(
            question=question,
            user_role=role,
            expected_mode="secure_rag",
            question_type="single_doc",
            gold_docs=[slug],
            gold_answer_points=[slug.replace("-", " ")],
            requires_permission=slug in {"confidential-supplier-contract", "finance-pricing-terms", "executive-summary"},
        )

    for i in range(1, 5):
        add(
            question=f"Public Supply Policy chunk {i % 2} 涉及哪些供应链合规要求？",
            user_role="procurement_staff",
            expected_mode="secure_rag",
            question_type="single_doc",
            gold_docs=["public-policy"],
        )

    # 2. Multi document synthesis
    multi_pairs = [
        (["public-policy", "internal-procurement-guide"], "综合公开政策和内部采购指南，总结供应商评估流程", "procurement_manager"),
        (["department-logistics-report", "quality-report"], "结合物流延迟和质量报告，分析 SUP-001 相关风险", "logistics_manager"),
        (["executive-summary", "department-logistics-report"], "高管摘要与物流报告中的延迟风险是否一致？", "executive"),
        (["quality-report", "confidential-supplier-contract"], "质量报告与机密合同对 SUP-001 的要求有何关联？", "procurement_manager"),
    ]
    for docs, question, role in multi_pairs:
        add(
            question=question,
            user_role=role,
            expected_mode="secure_rag",
            question_type="multi_doc",
            gold_docs=docs,
            requires_permission="confidential" in " ".join(docs),
        )
    for i in range(6):
        add(
            question=f"多文档综合：公开政策与物流报告对交付 SLA 的要求（变体 {i + 1}）",
            user_role="logistics_manager",
            expected_mode="secure_rag",
            question_type="multi_doc",
            gold_docs=["public-policy", "department-logistics-report"],
        )

    # 3. Contract clauses
    for i, role in enumerate(["procurement_manager", "finance_manager", "admin"]):
        add(
            question=f"机密供应商框架合同中关于违约条款的说明（场景 {i + 1}）",
            user_role=role,
            expected_mode="secure_rag",
            question_type="contract",
            gold_docs=["confidential-supplier-contract"],
            requires_permission=True,
        )
    for i in range(5):
        add(
            question=f"合同条款：SUP-001 框架协议中的质量验收标准（变体 {i + 1}）",
            user_role="procurement_manager",
            expected_mode="secure_rag",
            question_type="contract",
            gold_docs=["confidential-supplier-contract"],
            requires_permission=True,
        )

    # 4. Logistics delay
    for i in range(8):
        add(
            question=f"SUP-001 港口拥堵导致的物流延迟会影响哪些订单？（变体 {i + 1}）",
            user_role="logistics_manager",
            expected_mode="graphrag",
            question_type="logistics",
            gold_entities=["SUP-001", "PO-2024-0001", "P001", "C001"],
            gold_graph_paths=[SUPPLIER_PATH],
            requires_graph=True,
            graph_query_type="delivery_delay_impact",
            entity_code="SUP-001",
        )

    # 5. Quality issues
    for i in range(8):
        add(
            question=f"质量异常 QI-001 追溯到哪些产品和供应商？（变体 {i + 1}）",
            user_role="quality_manager",
            expected_mode="graphrag",
            question_type="quality",
            gold_entities=["QI-001", "SUP-001", "M002", "P001"],
            requires_graph=True,
            graph_query_type="quality_issue_trace",
            entity_code="QI-001",
        )

    # 6. Supplier risk
    for code in ["SUP-001", "SUP-002", "SUP-003"]:
        add(
            question=f"供应商 {code} 延迟会影响哪些材料、产品和客户？",
            user_role="procurement_manager",
            expected_mode="graphrag",
            question_type="supplier_risk",
            gold_entities=[code, "M001", "P001", "C001"],
            gold_graph_paths=[SUPPLIER_PATH],
            requires_graph=True,
            graph_query_type="supplier_impact",
            entity_code=code,
        )
    for i in range(7):
        add(
            question=f"评估 SUP-004 供应中断对 P001 的风险（变体 {i + 1}）",
            user_role="procurement_manager",
            expected_mode="graphrag",
            question_type="supplier_risk",
            gold_entities=["SUP-004", "M001", "P001"],
            requires_graph=True,
            graph_query_type="supplier_impact",
            entity_code="SUP-004",
        )

    # 7. GraphRAG multi-hop
    graph_types = [
        ("supplier_impact", "SUP-001", ["SUP-001", "M001", "P001", "PO-2024-0001", "C001"]),
        ("product_dependency", "P001", ["P001", "M001", "SUP-001"]),
        ("customer_order_dependency", "C001", ["C001", "PO-2024-0001", "P001"]),
        ("delivery_delay_impact", "SUP-001", ["SUP-001", "DE-001", "PO-2024-0001"]),
        ("quality_issue_trace", "QI-001", ["QI-001", "SUP-001", "M002"]),
    ]
    for qtype, entity, entities in graph_types:
        for i in range(3):
            add(
                question=f"GraphRAG 多跳：{qtype} 查询 {entity} 影响路径（变体 {i + 1}）",
                user_role="procurement_manager",
                expected_mode="graphrag",
                question_type="graphrag",
                gold_entities=entities,
                gold_graph_paths=[SUPPLIER_PATH] if qtype == "supplier_impact" else [],
                requires_graph=True,
                graph_query_type=qtype,
                entity_code=entity,
            )

    # 8. Alternatives
    for i in range(5):
        add(
            question=f"SUP-001 有哪些替代供应商？（变体 {i + 1}）",
            user_role="procurement_manager",
            expected_mode="graphrag",
            question_type="alternatives",
            gold_entities=["SUP-001", "SUP-004"],
            requires_graph=True,
            graph_query_type="supplier_alternatives",
            entity_code="SUP-001",
        )

    # 9. Permission isolation (required cases)
    add(
        question="机密供应商框架合同的 Net 60 付款条款是什么？",
        user_role="procurement_staff",
        expected_mode="secure_rag",
        question_type="permission_boundary",
        gold_docs=["confidential-supplier-contract"],
        requires_permission=True,
        should_be_blocked=True,
    )
    add(
        question="财务定价条款中的 Volume discount tier 1 是多少？",
        user_role="logistics_manager",
        expected_mode="secure_rag",
        question_type="permission_boundary",
        gold_docs=["finance-pricing-terms"],
        requires_permission=True,
        should_be_blocked=True,
    )
    add(
        question="Other Supplier Portal Notice 中的 Beta Materials 交付信息",
        user_role="external_supplier",
        expected_mode="secure_rag",
        question_type="external_supplier",
        gold_docs=["supplier-portal-sup002"],
        requires_permission=True,
        should_be_blocked=True,
    )
    add(
        question="Executive Risk Summary 中的整体供应链风险评级",
        user_role="executive",
        expected_mode="secure_rag",
        question_type="single_doc",
        gold_docs=["executive-summary"],
        requires_permission=True,
        should_be_blocked=False,
    )
    add(
        question="admin 查询 Finance Pricing Terms 的 18% margin 条款",
        user_role="admin",
        expected_mode="secure_rag",
        question_type="single_doc",
        gold_docs=["finance-pricing-terms"],
        requires_permission=True,
        should_be_blocked=False,
    )
    for role, slug, blocked in [
        ("procurement_staff", "finance-pricing-terms", True),
        ("logistics_manager", "confidential-supplier-contract", True),
        ("external_supplier", "supplier-portal-sup002", True),
        ("executive", "finance-pricing-terms", True),
        ("admin", "confidential-supplier-contract", False),
    ]:
        add(
            question=f"权限测试：{role} 访问 {slug}",
            user_role=role,
            expected_mode="secure_rag",
            question_type="permission_boundary",
            gold_docs=[slug],
            requires_permission=True,
            should_be_blocked=blocked,
        )

    # 10. Memory follow-up
    for i in range(5):
        session_id = f"bench-mem-{i + 1}"
        add(
            question=f"我们刚才讨论的供应商 SUP-001 延迟会影响哪些客户？（追问 {i + 1}）",
            user_role="procurement_manager",
            expected_mode="secure_rag",
            question_type="memory_followup",
            gold_entities=["SUP-001", "C001"],
            requires_memory=True,
            follow_up_session_id=session_id,
            session_seed=[
                {"role": "user", "content": "请分析 SUP-001 的交付延迟风险", "entities": {"supplier": "SUP-001"}},
                {"role": "assistant", "content": "SUP-001 延迟影响 M001、P001 及客户 C001 的订单 PO-2024-0001"},
            ],
        )

    for i in range(5):
        session_id = f"bench-mem-log-{i + 1}"
        add(
            question=f"继续上一个话题：该延迟事件影响了哪些订单？（物流追问 {i + 1}）",
            user_role="logistics_manager",
            expected_mode="secure_rag",
            question_type="memory_followup",
            gold_entities=["PO-2024-0001", "SUP-001"],
            requires_memory=True,
            follow_up_session_id=session_id,
            session_seed=[
                {"role": "user", "content": "DE-001 港口拥堵延迟情况", "entities": {"supplier": "SUP-001"}},
                {"role": "assistant", "content": "DE-001 关联 SUP-001，影响订单 PO-2024-0001"},
            ],
        )

    # 11. Unanswerable / refuse
    for i in range(10):
        add(
            question=f"2030 年火星基地供应商名单是什么？（无答案 {i + 1}）",
            user_role="procurement_manager",
            expected_mode="no_answer",
            question_type="unanswerable",
            gold_docs=[],
            gold_chunks=[],
            should_be_blocked=False,
        )

    # 12. External supplier scope
    for i in range(5):
        add(
            question=f"SUP-002 的门户通知内容是什么？（越权 {i + 1}）",
            user_role="external_supplier",
            expected_mode="secure_rag",
            question_type="external_supplier",
            gold_docs=["supplier-portal-sup002"],
            requires_permission=True,
            should_be_blocked=True,
        )

    return items


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    questions = build_questions()
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for item in questions:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Wrote {len(questions)} eval questions to {OUTPUT}")


if __name__ == "__main__":
    main()
