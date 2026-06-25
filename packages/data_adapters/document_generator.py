"""Generate synthetic enterprise documents from normalized real supply chain data."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from packages.data_adapters.utils import fix_mojibake


def _read(normalized_dir: Path, name: str) -> pd.DataFrame:
    path = normalized_dir / f"{name}.csv"
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def _doc_spec(
    filename: str,
    title: str,
    doc_type: str,
    security_level: str,
    security_level_rank: int,
    access_scope: str,
    department: str,
    allowed_roles: list[str] | None = None,
    supplier_code: str | None = None,
    source_dataset: str = "generated",
) -> dict[str, Any]:
    return {
        "filename": filename,
        "title": title,
        "doc_type": doc_type,
        "security_level": security_level,
        "security_level_rank": security_level_rank,
        "access_scope": access_scope,
        "department": department,
        "allowed_roles": allowed_roles or [],
        "supplier_code": supplier_code,
        "source_dataset": source_dataset,
        "generated": True,
        "disclaimer": "Simulation document derived from open dataset facts — not a real enterprise contract.",
    }


def generate_documents(
    normalized_dir: Path,
    output_dir: Path,
    *,
    max_suppliers: int = 20,
    max_delay_reports: int = 15,
) -> dict[str, Any]:
    """Write markdown/text documents + manifest.json."""
    normalized_dir = Path(normalized_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    suppliers = _read(normalized_dir, "suppliers")
    orders = _read(normalized_dir, "orders")
    deliveries = _read(normalized_dir, "deliveries")
    risks = _read(normalized_dir, "risk_events")
    products = _read(normalized_dir, "products")

    manifest: list[dict[str, Any]] = []

    # 1. Procurement policy (public/internal)
    policy_text = """# Procurement Policy (Generated from Real Dataset Summary)

This policy summary is auto-generated from open supply chain datasets (DataCo, SCMS, SupplyGraph).
It does NOT replace official corporate policy.

## Key Rules
- All procurement actions must reference auditable order and delivery records.
- Delivery delay events with severity >= high require logistics review within 48 hours.
- Supplier risk scores must be reviewed when risk_events exceed threshold.

## Data Sources
- Order and customer facts: DataCo Supply Chain Dataset
- Supplier and freight facts: SCMS Delivery History
- Graph dependencies: SupplyGraph heterogeneous network
"""
    policy_file = "procurement-policy-generated.md"
    (output_dir / policy_file).write_text(policy_text, encoding="utf-8")
    manifest.append(
        _doc_spec(
            policy_file,
            "Procurement Policy (Generated from Real Data)",
            "policy",
            "internal",
            1,
            "role_based",
            "procurement",
            allowed_roles=["procurement_manager", "procurement_staff", "admin"],
            source_dataset="dataco+scms",
        )
    )

    # 2. Supplier contract summaries (top SCMS suppliers)
    scms_suppliers = suppliers[suppliers.get("source_dataset") == "scms"].head(max_suppliers)
    if scms_suppliers.empty:
        scms_suppliers = suppliers.head(max_suppliers)

    for _, row in scms_suppliers.iterrows():
        code = str(row["supplier_code"])
        name = fix_mojibake(str(row["supplier_name"])) or code
        fname = f"supplier-contract-{code[:40].replace('/', '-')}.md"
        sup_orders = orders[orders.get("supplier_id") == row["supplier_id"]] if len(orders) else pd.DataFrame()
        order_count = len(sup_orders)
        text = f"""# Supplier Contract Summary (Simulated)

> **Disclaimer:** This is a simulation document generated from open dataset fields.
> It is NOT a real legal contract.

## Supplier
- Code: {code}
- Name: {name}
- Country: {fix_mojibake(str(row.get('country') or 'N/A'))}
- Source dataset: {row.get('source_dataset')}

## Derived Facts
- Active orders in normalized data: {order_count}
- Default payment term (simulated): Net 45 days
- Quality review cadence (simulated): Quarterly

## Notes
Payment and penalty clauses are illustrative placeholders for Secure RAG permission demos.
"""
        (output_dir / fname).write_text(text, encoding="utf-8")
        manifest.append(
            _doc_spec(
                fname,
                f"Supplier Contract Summary — {name}",
                "contract",
                "confidential",
                3,
                "role_based",
                "procurement",
                allowed_roles=["procurement_manager", "finance_manager", "admin"],
                supplier_code=code if code.startswith("SCMS-") else None,
                source_dataset=str(row.get("source_dataset")),
            )
        )

    # 3. Logistics delay reports
    late = deliveries.copy()
    if "delay_days" in late.columns:
        late = late[pd.to_numeric(late["delay_days"], errors="coerce").fillna(0) > 0]
    late = late.head(max_delay_reports)

    for i, (_, row) in enumerate(late.iterrows(), start=1):
        fname = f"logistics-delay-report-{i:03d}.md"
        text = f"""# Logistics Delay Report (Generated)

## Delivery Record
- Order ID: {row.get('order_id')}
- Shipment mode: {row.get('shipment_mode')}
- Origin: {row.get('origin_country')} → Destination: {row.get('destination_country')}
- Planned date: {row.get('planned_date')}
- Actual date: {row.get('actual_date')}
- Delay days: {row.get('delay_days')}
- Status: {row.get('delivery_status')}
- Source dataset: {row.get('source_dataset')}

## Analysis (Simulated)
Primary contributing factor recorded: {row.get('delay_reason') or 'schedule slip'}.
Recommend monitoring affected downstream orders linked in GraphRAG.
"""
        (output_dir / fname).write_text(text, encoding="utf-8")
        manifest.append(
            _doc_spec(
                fname,
                f"Logistics Delay Report #{i}",
                "logistics_report",
                "department",
                2,
                "department",
                "logistics",
                allowed_roles=["logistics_manager", "procurement_manager"],
                source_dataset=str(row.get("source_dataset")),
            )
        )

    # 4. Quality inspection report (from product/material sample)
    mat = _read(normalized_dir, "materials").head(5)
    qual_file = "quality-inspection-report-generated.md"
    lines = ["# Quality Inspection Report (Generated)\n"]
    for _, m in mat.iterrows():
        lines.append(f"- Material {m.get('material_code')}: category={m.get('category')}, critical={m.get('is_critical')}")
    lines.append("\nSimulated pass rate: 98.7% (illustrative).\n")
    (output_dir / qual_file).write_text("\n".join(lines), encoding="utf-8")
    manifest.append(
        _doc_spec(
            qual_file,
            "Quality Inspection Report (Generated)",
            "quality_report",
            "confidential",
            3,
            "role_based",
            "quality",
            allowed_roles=["quality_manager", "procurement_manager"],
            source_dataset="supplygraph",
        )
    )

    # 5. Executive risk brief
    top_risks = risks.head(10)
    exec_file = "executive-risk-brief-generated.md"
    exec_lines = ["# Executive Risk Brief (Generated)\n", "## Top Risk Signals\n"]
    for _, r in top_risks.iterrows():
        exec_lines.append(
            f"- [{r.get('severity')}] {r.get('title')} ({r.get('event_type')}, source={r.get('source_dataset')})"
        )
    exec_lines.append("\n*Simulation based on open dataset risk_events — for executive dashboard demo.*\n")
    (output_dir / exec_file).write_text("\n".join(exec_lines), encoding="utf-8")
    manifest.append(
        _doc_spec(
            exec_file,
            "Executive Risk Brief (Generated)",
            "executive_summary",
            "executive",
            4,
            "executive_summary",
            "executive",
            allowed_roles=["executive", "admin"],
            source_dataset="dataco+scms",
        )
    )

    # 6. Supplier portal notice (first SCMS supplier if available)
    if len(scms_suppliers):
        srow = scms_suppliers.iloc[0]
        code = str(srow["supplier_code"])
        portal_file = f"supplier-portal-notice-{code[:24]}.md"
        (output_dir / portal_file).write_text(
            f"""# Supplier Portal Notice (Generated)

Supplier: {fix_mojibake(str(srow['supplier_name']))}
Code: {code}

Please review open delivery records and confirm updated ETA for pending orders.
This notice is scoped to supplier portal visibility demos only.
""",
            encoding="utf-8",
        )
        manifest.append(
            _doc_spec(
                portal_file,
                "Supplier Portal Notice (Generated)",
                "supplier_notice",
                "internal",
                1,
                "supplier_portal",
                "external",
                supplier_code=code if not code.startswith("PLANT-") else "SUP-001",
                source_dataset="scms",
            )
        )

    # 7. Supplier risk summary
    risk_summary = "supplier-risk-summary-generated.md"
    (output_dir / risk_summary).write_text(
        f"""# Supplier Risk Summary (Generated)

Total risk events in normalized store: {len(risks)}
Total suppliers: {len(suppliers)}
Total products: {len(products)}

Use GraphRAG for multi-hop impact analysis and Secure RAG for document-backed Q&A.
""",
        encoding="utf-8",
    )
    manifest.append(
        _doc_spec(
            risk_summary,
            "Supplier Risk Summary (Generated)",
            "risk_report",
            "confidential",
            3,
            "role_based",
            "procurement",
            allowed_roles=["procurement_manager", "quality_manager", "admin"],
            source_dataset="merged",
        )
    )

    # 8. Compliance screening memo (placeholder without OFAC)
    comp_file = "compliance-screening-memo-generated.md"
    (output_dir / comp_file).write_text(
        """# Compliance Screening Memo (Generated)

No OFAC dataset loaded in this environment.
This memo describes the screening workflow only:

1. Match supplier names against sanctions lists (potential_match flag)
2. Require human review before any automated denial
3. Log all decisions to audit trail

*Simulation document — not a legal compliance determination.*
""",
        encoding="utf-8",
    )
    manifest.append(
        _doc_spec(
            comp_file,
            "Compliance Screening Memo (Generated)",
            "compliance_memo",
            "confidential",
            3,
            "role_based",
            "procurement",
            allowed_roles=["procurement_manager", "finance_manager", "admin"],
            source_dataset="generated",
        )
    )

    meta = {
        "generated_at": datetime.now(UTC).isoformat(),
        "document_count": len(manifest),
        "output_dir": str(output_dir),
        "documents": manifest,
    }
    (output_dir / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta
