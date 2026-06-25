#!/usr/bin/env python3
"""Load normalized real-data CSVs into PostgreSQL."""

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

from packages.common.db.session import get_session_factory
from packages.data_adapters.postgres_loader import load_real_data_to_postgres


async def run(args: argparse.Namespace) -> dict:
    session_factory = get_session_factory()
    async with session_factory() as session:
        report = await load_real_data_to_postgres(
            session,
            args.normalized_dir,
            limit=args.limit,
            dry_run=args.dry_run,
            reset=args.reset_real_data,
        )
        if not args.dry_run:
            await session.commit()
        else:
            await session.rollback()
    return report.to_dict()


def main() -> int:
    parser = argparse.ArgumentParser(description="Load normalized data into PostgreSQL")
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=ROOT / "data" / "generated" / "normalized",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per entity (dev)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without commit")
    parser.add_argument("--reset-real-data", action="store_true", help="Delete prior real-data rows")
    args = parser.parse_args()

    if not args.normalized_dir.exists():
        print(f"ERROR: normalized dir not found: {args.normalized_dir}", file=sys.stderr)
        return 1

    result = asyncio.run(run(args))
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "normalized_dir": str(args.normalized_dir.resolve()),
        **result,
    }
    out = args.normalized_dir.parent / "load_real_data_summary.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Load real data summary:")
    print(json.dumps(result, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
