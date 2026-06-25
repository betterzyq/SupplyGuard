#!/usr/bin/env python3
"""Generate synthetic enterprise documents from normalized real data."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.data_adapters.document_generator import generate_documents


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate realistic documents from normalized data")
    parser.add_argument(
        "--normalized-dir",
        type=Path,
        default=ROOT / "data" / "generated" / "normalized",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "generated" / "documents",
    )
    parser.add_argument("--max-suppliers", type=int, default=20)
    args = parser.parse_args()

    if not args.normalized_dir.exists():
        print(f"ERROR: {args.normalized_dir} not found. Run make normalize-data first.", file=sys.stderr)
        return 1

    meta = generate_documents(
        args.normalized_dir,
        args.output_dir,
        max_suppliers=args.max_suppliers,
    )
    print(json.dumps({"document_count": meta["document_count"], "output_dir": meta["output_dir"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
