#!/usr/bin/env python3
"""Ingest generated real-data documents into PostgreSQL and Qdrant."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from packages.authz.constants import security_level_to_rank
from packages.common.db.models.document import Document
from packages.common.db.models.supplier import Supplier
from packages.common.db.models.tenant import Tenant
from packages.common.db.models.user import User
from packages.common.db.session import get_session_factory
from packages.rag.ingest import index_document_text, parse_file

TENANT_CODE = "demo-mfg"
DOCS_DIR = ROOT / "data" / "generated" / "documents"


async def ingest_real_docs(docs_dir: Path | None = None, *, reindex: bool = False, limit: int | None = None) -> dict:
    docs_dir = Path(docs_dir or DOCS_DIR)
    manifest_path = docs_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest not found: {manifest_path}. Run make generate-real-docs first.")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    session_factory = get_session_factory()

    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.code == TENANT_CODE))
        ).scalar_one()
        admin = (
            await session.execute(
                select(User).where(User.tenant_id == tenant.id, User.email == "admin@example.com")
            )
        ).scalar_one()

        supplier_by_code = {
            s.code: s.id
            for s in (await session.execute(select(Supplier).where(Supplier.tenant_id == tenant.id))).scalars()
        }

        indexed = 0
        skipped = 0
        docs = manifest.get("documents", [])
        if limit is not None:
            docs = docs[:limit]
        for spec in docs:
            filename = spec["filename"]
            path = docs_dir / filename
            if not path.exists():
                skipped += 1
                continue

            source_uri = str(path.resolve().relative_to(ROOT.resolve()))
            existing = (
                await session.execute(
                    select(Document).where(
                        Document.tenant_id == tenant.id,
                        Document.source_uri == source_uri,
                    )
                )
            ).scalar_one_or_none()

            supplier_id = None
            scode = spec.get("supplier_code")
            if scode and scode in supplier_by_code:
                supplier_id = supplier_by_code[scode]

            if existing is None:
                doc = Document(
                    tenant_id=tenant.id,
                    title=spec["title"],
                    doc_type=spec["doc_type"],
                    source_uri=source_uri,
                    file_name=filename,
                    mime_type="text/markdown" if filename.endswith(".md") else "text/plain",
                    security_level=spec["security_level"],
                    security_level_rank=spec.get("security_level_rank")
                    or security_level_to_rank(spec["security_level"]),
                    access_scope=spec["access_scope"],
                    department=spec.get("department") or "procurement",
                    allowed_roles=spec.get("allowed_roles") or [],
                    allowed_users=[],
                    supplier_id=supplier_id,
                    status="pending",
                    metadata_={
                        "real_data": True,
                        "generated": True,
                        "source_dataset": spec.get("source_dataset"),
                        "disclaimer": spec.get("disclaimer"),
                    },
                    uploaded_by=admin.id,
                )
                session.add(doc)
                await session.flush()
            else:
                doc = existing
                if not reindex:
                    skipped += 1
                    continue

            text = parse_file(path)
            chunk_count = await index_document_text(session, doc, text, reindex=True)
            doc.status = "indexed"
            indexed += 1
            print(f"  indexed: {doc.title} ({chunk_count} chunks)")

        await session.commit()
        return {"indexed": indexed, "skipped": skipped, "total": len(docs)}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--docs-dir", type=Path, default=DOCS_DIR)
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Max documents to ingest (dev)")
    args = parser.parse_args()

    result = asyncio.run(ingest_real_docs(args.docs_dir, reindex=args.reindex, limit=args.limit))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
