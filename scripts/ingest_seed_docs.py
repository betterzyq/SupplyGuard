#!/usr/bin/env python3
"""Ingest seed documents with real text into PostgreSQL and Qdrant."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

from packages.common.db.models.document import Document  # noqa: E402
from packages.common.db.models.tenant import Tenant  # noqa: E402
from packages.common.db.session import get_session_factory  # noqa: E402
from packages.rag.ingest import DATA_DIR, raw_dir, reindex_existing_document  # noqa: E402

TENANT_CODE = "demo-mfg"

SEED_CONTENT: dict[str, str] = {
    "public-policy": """
Public Supply Policy
All suppliers must comply with the company code of conduct.
Delivery performance is reviewed quarterly.
""",
    "internal-procurement-guide": """
Internal Procurement Guide
Procurement staff must obtain three quotes for orders above USD 50,000.
Preferred payment term baseline is Net 45 days.
""",
    "department-logistics-report": """
Logistics Delay Analysis Report - March 2024
Primary cause of recent delays: port congestion at Shanghai.
Average inbound shipment delay: 5 days.
Affected lanes include CN-US and CN-EU routes.
""",
    "confidential-supplier-contract": """
Confidential Supplier Framework Contract
Supplier: Alpha Components Ltd. (SUP-001)
Payment terms: Net 60 days from invoice date.
Late delivery penalty: 2% of order value per week.
Quality acceptance threshold: 99.2% pass rate.
""",
    "finance-pricing-terms": """
Finance Pricing Terms (Confidential)
Standard gross margin target: 18%.
Volume discount tier 1: 3% for orders above USD 500,000.
Currency settlement default: USD.
""",
    "quality-report": """
Supplier Quality Inspection Report
Supplier Alpha Components Ltd. inspection pass rate: 99.4%.
Top defect category: dimensional tolerance on batch QC-2024-03.
""",
    "executive-summary": """
Executive Risk Summary
Top supply chain risks this quarter: logistics congestion and tier-1 supplier concentration.
Recommended action: diversify two critical component suppliers within 90 days.
""",
    "supplier-portal-sup001": """
Supplier Portal Delivery Notice
Supplier: Alpha Components Ltd. (SUP-001)
Next scheduled delivery date: 2024-07-15
Quantity: 1200 units of Component-A
""",
    "supplier-portal-sup002": """
Supplier Portal Delivery Notice
Supplier: Beta Materials Inc. (SUP-002)
Next scheduled delivery date: 2024-08-01
Quantity: 800 units of Component-B
""",
}


async def ingest_seed_docs() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.code == TENANT_CODE))
        ).scalar_one_or_none()
        if tenant is None:
            raise RuntimeError("Tenant demo-mfg not found. Run `make seed` first.")

        documents = (
            await session.execute(
                select(Document).where(Document.tenant_id == tenant.id)
            )
        ).scalars().all()

        slug_map = {
            (doc.metadata_ or {}).get("slug"): doc
            for doc in documents
            if (doc.metadata_ or {}).get("slug")
        }

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        for slug, content in SEED_CONTENT.items():
            document = slug_map.get(slug)
            if document is None:
                print(f"[SKIP] document slug not found: {slug}")
                continue

            filename = f"{slug}.txt"
            raw_path = raw_dir(document.tenant_id, document.id) / filename
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(content.strip() + "\n", encoding="utf-8")
            document.file_name = filename
            document.source_uri = str(raw_path.relative_to(ROOT))

            chunk_count = await reindex_existing_document(
                session,
                document.id,
                text=content.strip(),
                chunk_size=512,
            )
            await session.commit()
            print(f"[OK] {slug}: chunks={chunk_count}")


if __name__ == "__main__":
    asyncio.run(ingest_seed_docs())
