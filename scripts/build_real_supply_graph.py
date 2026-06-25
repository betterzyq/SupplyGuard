#!/usr/bin/env python3
"""Build Neo4j graph from normalized real-data (additive; marks real_data nodes)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from packages.common.db.models.tenant import Tenant
from packages.common.db.session import get_session_factory
from packages.data_adapters.graph_loader import build_real_graph_from_normalized, reset_real_graph

TENANT_CODE = "demo-mfg"


async def run(args: argparse.Namespace) -> dict:
    session_factory = get_session_factory()
    async with session_factory() as session:
        tenant = (
            await session.execute(select(Tenant).where(Tenant.code == TENANT_CODE))
        ).scalar_one_or_none()
        if tenant is None:
            raise RuntimeError(f"Tenant {TENANT_CODE} not found. Run make seed first.")
        tenant_id = str(tenant.id)

    if args.reset_graph:
        print("[*] Resetting real_data nodes in Neo4j...")
        await reset_real_graph(tenant_id)

    print("[*] Building real supply graph...")
    stats = await build_real_graph_from_normalized(
        tenant_id,
        args.normalized_dir,
        limit=args.limit,
    )
    return {"tenant_id": tenant_id, "stats": stats}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Neo4j graph from normalized CSVs")
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=ROOT / "data" / "generated" / "normalized",
    )
    parser.add_argument("--limit", type=int, default=5000, help="Max orders/deliveries/risks for graph")
    parser.add_argument("--reset-graph", action="store_true", help="Remove prior real_data graph nodes")
    args = parser.parse_args()

    if not args.normalized_dir.exists():
        print(f"ERROR: {args.normalized_dir} not found", file=sys.stderr)
        return 1

    result = asyncio.run(run(args))
    summary = {"generated_at": datetime.now(UTC).isoformat(), **result}
    out = args.normalized_dir.parent / "build_real_graph_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Graph stats:")
    for k, v in result["stats"].items():
        print(f"  {k}: {v}")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
