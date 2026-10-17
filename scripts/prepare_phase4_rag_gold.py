#!/usr/bin/env python3
"""Seed-text span annotations; no DB mutation, embeddings or re-indexing."""

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "scripts/ingest_seed_docs.py"
for node in ast.parse(source.read_text()).body:
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "SEED_CONTENT"
    ):
        content = ast.literal_eval(node.value)
questions = [
    (
        "public-policy",
        "供应商交付表现的复核频率是多少？",
        "Delivery performance is reviewed quarterly.",
    ),
    (
        "internal-procurement-guide",
        "采购额超过多少需要获取三份报价？",
        "Procurement staff must obtain three quotes for orders above USD 50,000.",
    ),
    (
        "department-logistics-report",
        "2024年3月物流报告的平均入境运输延误天数是多少？",
        "Average inbound shipment delay: 5 days.",
    ),
    (
        "confidential-supplier-contract",
        "SUP-001 框架合同的逾期交付罚款如何计算？",
        "Late delivery penalty: 2% of order value per week.",
    ),
    (
        "finance-pricing-terms",
        "订单达到一级批量折扣的金额门槛和折扣是多少？",
        "Volume discount tier 1: 3% for orders above USD 500,000.",
    ),
    (
        "quality-report",
        "Alpha 质量报告的检验合格率是多少？",
        "Supplier Alpha Components Ltd. inspection pass rate: 99.4%.",
    ),
    (
        "executive-summary",
        "管理层建议在多长时间内分散多少关键零件供应商？",
        "Recommended action: diversify two critical component suppliers within 90 days.",
    ),
    (
        "supplier-portal-sup001",
        "Alpha 下一批 Component-A 的计划交付日期与数量是多少？",
        "Next scheduled delivery date: 2024-07-15\nQuantity: 1200 units of Component-A",
    ),
    (
        "supplier-portal-sup002",
        "Beta 下一批 Component-B 的计划交付日期与数量是多少？",
        "Next scheduled delivery date: 2024-08-01\nQuantity: 800 units of Component-B",
    ),
]
rows = []
for i, (slug, q, span) in enumerate(questions, 1):
    assert span in content[slug]
    rows.append(
        {
            "id": f"enterprise-rag-{i:03d}",
            "dataset_version": "rag-enterprise-v2",
            "policy_version": "enterprise-v2",
            "question": q,
            "user_role": "enterprise",
            "expected_mode": "secure_rag",
            "question_type": "span_grounded",
            "requires_permission": True,
            "should_be_blocked": False,
            "gold_docs": [slug],
            "gold_spans": [
                {
                    "slug": slug,
                    "text": span,
                    "source_text_sha256": hashlib.sha256(
                        content[slug].strip().encode()
                    ).hexdigest(),
                }
            ],
            "gold_answer_points": [span],
            "annotation_basis": "reviewed repository seed text; live chunks must resolve exact span; not yet live-evaluated",
        }
    )
path = ROOT / "data/eval/rag-enterprise-v2.jsonl"
text = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows)
if path.exists() and path.read_text() != text:
    raise SystemExit("Existing version changed; create a new annotation version")
path.write_text(text)
print("Exact source-span annotations", len(rows))
