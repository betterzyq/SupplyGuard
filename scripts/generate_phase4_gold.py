#!/usr/bin/env python3
"""Versioned seed-derived graph gold and strict scorer/policy contract cases."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
seed_path = ROOT / "data/seed/graph_seed.json"
seed = json.loads(seed_path.read_text())
cases = []
for supplier in sorted({r["supplier_code"] for r in seed["supplies"]}):
    paths = []
    for supply in seed["supplies"]:
        if supply["supplier_code"] != supplier:
            continue
        for link in seed["used_in"]:
            if link["material_code"] != supply["material_code"]:
                continue
            for order in seed["order_links"]:
                if order["product_code"] == link["product_code"]:
                    paths.append(
                        [
                            "Supplier:" + supplier,
                            "Material:" + link["material_code"],
                            "Product:" + link["product_code"],
                            "Order:" + order["order_no"],
                            "Customer:" + order["customer_code"],
                        ]
                    )
    cases.append(
        {
            "id": "impact-" + supplier,
            "kind": "graph_gold",
            "query_type": "supplier_impact",
            "entity_code": supplier,
            "gold_graph_paths": paths,
        }
    )
for row in seed["delivery_events"]:
    if row["status"] == "delayed":
        cases.append(
            {
                "id": "delay-" + row["id"],
                "kind": "graph_gold",
                "query_type": "delivery_delay",
                "entity_code": row["supplier_code"],
                "gold_graph_paths": [
                    [
                        "Supplier:" + row["supplier_code"],
                        "DeliveryEvent:" + row["id"],
                        "Order:" + row["order_no"],
                    ]
                ],
            }
        )
for row in seed["alternatives"]:
    cases.append(
        {
            "id": "alternative-" + row["supplier_code"],
            "kind": "graph_gold",
            "query_type": "supplier_alternatives",
            "entity_code": row["supplier_code"],
            "gold_graph_paths": [
                [
                    "Supplier:" + row["supplier_code"],
                    "Supplier:" + row["alternative_code"],
                ]
            ],
        }
    )
for role in ["admin", "enterprise"]:
    for scope, resource, expected in [
        ("same_tenant", "document", "allow"),
        ("other_tenant", "document", "denied"),
        ("same_tenant", "admin", "allow" if role == "admin" else "denied"),
    ]:
        cases.append(
            {
                "id": f"policy-{role}-{scope}-{resource}",
                "kind": "policy",
                "role": role,
                "scope": scope,
                "resource": resource,
                "expected_decision": expected,
            }
        )
# Explicit observed outputs are intentionally separate from graph gold.
cases += [
    {
        "id": "path-supplier-prefix",
        "kind": "path_scorer",
        "found": ["Supplier SUP-0011 → Material M001"],
        "gold": [["Supplier:SUP-001", "Material:M001"]],
        "expected": 0,
    },
    {
        "id": "path-partial",
        "kind": "path_scorer",
        "found": ["Supplier SUP-001"],
        "gold": [["Supplier:SUP-001", "Material:M001"]],
        "expected": 0,
    },
    {
        "id": "path-reversed",
        "kind": "path_scorer",
        "found": ["Material M001 → Supplier SUP-001"],
        "gold": [["Supplier:SUP-001", "Material:M001"]],
        "expected": 0,
    },
    {
        "id": "path-wrong-type",
        "kind": "path_scorer",
        "found": ["Supplier SUP-001 → Product M001"],
        "gold": [["Supplier:SUP-001", "Material:M001"]],
        "expected": 0,
    },
    {
        "id": "path-exact",
        "kind": "path_scorer",
        "found": ["Supplier SUP-001 → SUPPLIES → Material M001"],
        "gold": [["Supplier:SUP-001", "Material:M001"]],
        "expected": 1,
    },
    {
        "id": "citation-prefix",
        "kind": "citation_scorer",
        "found": [{"chunk_id": "doc#11"}],
        "gold": ["doc#1"],
        "precision": 0,
        "recall": 0,
    },
    {
        "id": "citation-extra",
        "kind": "citation_scorer",
        "found": [{"chunk_id": "a"}, {"chunk_id": "b"}],
        "gold": ["a"],
        "precision": 0.5,
        "recall": 1,
    },
    {
        "id": "citation-missing",
        "kind": "citation_scorer",
        "found": [{"chunk_id": "a"}],
        "gold": ["a", "b"],
        "precision": 1,
        "recall": 0.5,
    },
    {
        "id": "no-evidence-is-not-denial",
        "kind": "denial_scorer",
        "decision": "no_evidence",
        "expected": 0,
    },
    {
        "id": "actual-denial",
        "kind": "denial_scorer",
        "decision": "denied",
        "expected": 1,
    },
    {
        "id": "error-is-not-denial",
        "kind": "denial_scorer",
        "decision": "error",
        "expected": 0,
    },
]
value = {
    "dataset_version": "enterprise-eval-v2",
    "policy_version": "enterprise-v2",
    "scorer_version": "enterprise-scorer-v2",
    "purpose": "offline scorer/policy contracts; seed-derived graph gold, not live retrieval quality or LLM answer accuracy",
    "seed_sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
    "cases": cases,
}
path = ROOT / "data/eval/enterprise-v2.json"
if (
    path.exists()
    and path.read_text() != json.dumps(value, ensure_ascii=False, indent=2) + "\n"
):
    raise SystemExit(
        "Existing version differs; create a new gold version rather than silently replacing"
    )
path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
print("Versioned cases", len(cases))

# Ready-to-run GraphRAG annotations, separate from scorer contract observations.
graph_rows = []
for c in cases:
    if c["kind"] != "graph_gold":
        continue
    query_type = c["query_type"]
    code = c["entity_code"]
    question = {
        "supplier_impact": f"{code} 会通过哪些物料、产品和订单影响哪些客户？",
        "delivery_delay": f"{code} 已登记的延迟交付事件关联哪些订单？",
        "supplier_alternatives": f"{code} 已登记的替代供应商有哪些？",
    }[query_type]
    paths = c["gold_graph_paths"]
    graph_rows.append(
        {
            "id": "enterprise-graph-" + c["id"],
            "question": question,
            "user_role": "enterprise",
            "dataset_version": "graph-enterprise-v2",
            "policy_version": "enterprise-v2",
            "expected_mode": "graphrag",
            "question_type": "graphrag",
            "requires_graph": True,
            "requires_permission": True,
            "graph_query_type": query_type,
            "entity_code": code,
            "gold_graph_paths": paths,
            "gold_entities": sorted(
                {n.split(":", 1)[1] for path in paths for n in path}
            ),
            "annotation_basis": "exact seed joins; verify current tenant graph matches seed version before live scoring",
            "seed_sha256": value["seed_sha256"],
        }
    )
graph_path = ROOT / "data/eval/graph-enterprise-v2.jsonl"
graph_text = "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in graph_rows)
if graph_path.exists() and graph_path.read_text() != graph_text:
    raise SystemExit("Existing graph annotations changed; create a new version")
graph_path.write_text(graph_text)
print("Ready-to-run graph questions", len(graph_rows))
