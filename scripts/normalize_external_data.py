#!/usr/bin/env python3
"""Normalize external datasets into SupplyGuard standard CSV tables."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.data_adapters.dataco_adapter import build_dataco_adapter
from packages.data_adapters.graph_seed_generator import export_graph_seed_preview
from packages.data_adapters.merger import link_orders_to_graph, link_scms_suppliers_to_graph, merge_normalized
from packages.data_adapters.optional_adapters import build_optional_adapters
from packages.data_adapters.quality_checks import validate_normalized_dir
from packages.data_adapters.schema import NORMALIZED_TABLE_NAMES
from packages.data_adapters.scms_adapter import build_scms_adapter
from packages.data_adapters.supplygraph_adapter import build_supplygraph_adapter


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize external datasets")
    parser.add_argument("--external-dir", type=Path, default=ROOT / "data" / "external")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "generated" / "normalized")
    parser.add_argument("--limit", type=int, default=None, help="Limit rows per source file (dev)")
    args = parser.parse_args()

    external_dir = args.external_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    adapters = []
    for builder in (build_dataco_adapter, build_scms_adapter, build_supplygraph_adapter):
        adapter = builder(external_dir, limit=args.limit)
        if adapter:
            print(f"[+] Detected adapter: {adapter.dataset_name} ({len(adapter.file_paths)} files)")
            adapters.append(adapter)
        else:
            print(f"[-] Adapter not found: {builder.__name__}")

    optional = build_optional_adapters(external_dir, limit=args.limit)
    for adapter in optional:
        print(f"[+] Optional adapter: {adapter.dataset_name} ({len(adapter.file_paths)} files)")
        adapters.append(adapter)

    if not adapters:
        print("ERROR: No adapters detected. Run make profile-data first.", file=sys.stderr)
        return 1

    normalized_parts = []
    reports = []
    for adapter in adapters:
        print(f"[*] Transforming {adapter.dataset_name}...")
        norm = adapter.transform()
        validation = adapter.validate()
        reports.append(
            {
                "dataset": adapter.dataset_name,
                "passed": validation.passed,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "stats": validation.stats,
            }
        )
        if validation.errors:
            print(f"  ERRORS: {validation.errors}")
        if validation.warnings:
            print(f"  WARN: {validation.warnings}")
        print(f"  Stats: {validation.stats}")
        normalized_parts.append(norm)

    merged = merge_normalized(normalized_parts)
    merged = link_orders_to_graph(merged)
    merged = link_scms_suppliers_to_graph(merged)

    print(f"[*] Writing merged tables to {output_dir}")
    stats: dict[str, int] = {}
    for name in NORMALIZED_TABLE_NAMES:
        df = merged.table(name)
        stats[name] = len(df)
        df.to_csv(output_dir / f"{name}.csv", index=False)
        if len(df) > 0:
            print(f"  {name}: {len(df):,} rows")
        else:
            print(f"  {name}: (empty)")

    preview_path = output_dir.parent / "graph_seed_preview.json"
    export_graph_seed_preview(output_dir, preview_path)

    quality = validate_normalized_dir(output_dir)
    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "external_dir": str(external_dir),
        "output_dir": str(output_dir),
        "limit": args.limit,
        "adapter_reports": reports,
        "row_counts": stats,
        "quality_checks": quality.checks,
        "quality_passed": quality.passed,
    }
    summary_path = output_dir.parent / "normalize_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[*] Summary: {summary_path}")

    if not quality.passed:
        print("WARNING: Some quality checks failed (see normalize_summary.json)", file=sys.stderr)
        return 2

    print("Normalize complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
