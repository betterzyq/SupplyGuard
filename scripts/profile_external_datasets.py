#!/usr/bin/env python3
"""Profile external open datasets under data/external/.

Scans CSV / XLSX / JSON / Parquet files, samples rows, detects likely dataset
types, and writes markdown + JSON reports. Does NOT load data into databases.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA_EXTENSIONS = {".csv", ".xlsx", ".xls", ".json", ".jsonl", ".parquet", ".pq"}
SKIP_DIR_NAMES = {".git", "__pycache__", "node_modules", ".venv"}
KNOWN_DATASETS = [
    "dataco",
    "scms",
    "supplygraph",
    "open_supply_hub",
    "gdelt",
    "ofac",
    "world_bank_lpi",
    "un_comtrade",
    "acled",
]

# Column hints for dataset auto-detection (normalized lowercase)
DATASET_COLUMN_HINTS: dict[str, list[str]] = {
    "dataco": [
        "order id",
        "late_delivery_risk",
        "delivery status",
        "days for shipping",
        "product name",
        "customer id",
        "shipping mode",
    ],
    "scms": [
        "vendor",
        "po sent to vendor date",
        "scheduled delivery date",
        "delivered to client date",
        "freight cost",
        "manufacturing site",
        "shipment mode",
    ],
    "supplygraph": [
        "node",
        "nodeindex",
        "plant",
        "storage location",
        "sub-group",
        "group",
    ],
    "open_supply_hub": [
        "facility",
        "latitude",
        "longitude",
        "sector",
        "os id",
    ],
    "gdelt": [
        "globaleventid",
        "actor1name",
        "actiongeo_countrycode",
        "eventcode",
    ],
    "ofac": [
        "sdn_name",
        "program",
        "sanction",
        "entity_number",
    ],
    "world_bank_lpi": [
        "lpi",
        "logistics performance",
        "country code",
        "score",
    ],
    "un_comtrade": [
        "reporter",
        "partner",
        "trade value",
        "commodity code",
        "qty",
    ],
    "acled": [
        "event_id_cnty",
        "event_type",
        "actor1",
        "fatalities",
        "latitude",
        "longitude",
    ],
}


def normalize_col(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower())


def count_csv_rows(path: Path) -> int:
    """Fast line count for CSV (excluding header)."""
    count = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return max(0, count - 1)


def read_tabular_sample(path: Path, sample_size: int) -> tuple[pd.DataFrame, str | None]:
    """Read up to sample_size rows; return dataframe and optional warning."""
    suffix = path.suffix.lower()
    warning: str | None = None
    try:
        if suffix == ".csv":
            for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
                try:
                    df = pd.read_csv(path, nrows=sample_size, encoding=encoding, low_memory=False)
                    return df, warning
                except UnicodeDecodeError:
                    continue
            df = pd.read_csv(path, nrows=sample_size, encoding="utf-8", errors="replace", low_memory=False)
            warning = "Used UTF-8 with replacement for undecodable bytes"
            return df, warning
        if suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(path, nrows=sample_size)
            return df, warning
        if suffix == ".json":
            with path.open(encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, list):
                df = pd.DataFrame(payload[:sample_size])
            elif isinstance(payload, dict):
                if "data" in payload and isinstance(payload["data"], list):
                    df = pd.DataFrame(payload["data"][:sample_size])
                else:
                    df = pd.json_normalize(payload)
                    df = df.head(sample_size)
            else:
                df = pd.DataFrame([payload])
            return df, warning
        if suffix == ".jsonl":
            rows: list[dict[str, Any]] = []
            with path.open(encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if i >= sample_size:
                        break
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            df = pd.DataFrame(rows)
            return df, warning
        if suffix in {".parquet", ".pq"}:
            df = pd.read_parquet(path)
            if len(df) > sample_size:
                df = df.head(sample_size)
                warning = f"Parquet sampled to first {sample_size} rows"
            return df, warning
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame(), f"Failed to read: {exc}"
    return pd.DataFrame(), f"Unsupported extension: {suffix}"


def estimate_row_count(path: Path, sample_df: pd.DataFrame, sampled_rows: int) -> int | None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            return count_csv_rows(path)
        except OSError:
            return sampled_rows if not sample_df.empty else None
    if suffix == ".jsonl":
        try:
            count = 0
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        count += 1
            return count
        except OSError:
            return sampled_rows if not sample_df.empty else None
    if not sample_df.empty:
        return len(sample_df)
    return None


def primary_dataset_from_path(path: Path, external_dir: Path) -> str | None:
    try:
        rel = path.relative_to(external_dir)
        if rel.parts and rel.parts[0] in KNOWN_DATASETS:
            return rel.parts[0]
    except ValueError:
        pass
    return None


def detect_dataset_type(path: Path, external_dir: Path, columns: list[str]) -> tuple[str, float, list[str]]:
    """Return (dataset_type, confidence 0-1, matched_signals)."""
    path_lower = str(path).lower()
    col_norm = {normalize_col(c) for c in columns}
    primary = primary_dataset_from_path(path, external_dir)

    scores: dict[str, float] = {}
    signals: dict[str, list[str]] = {}

    for ds in KNOWN_DATASETS:
        s = 0.0
        sig: list[str] = []
        if primary == ds:
            s += 0.55
            sig.append(f"root folder: {ds}/")
        elif f"/{ds}/" in path_lower:
            s += 0.35
            sig.append(f"path contains /{ds}/")
        hints = DATASET_COLUMN_HINTS.get(ds, [])
        if hints and columns:
            matched = [h for h in hints if h in col_norm]
            if matched:
                ratio = len(matched) / len(hints)
                s += 0.45 * ratio
                sig.extend([f"column:{m}" for m in matched])
        if s > 0:
            scores[ds] = s
            signals[ds] = sig

    # SupplyGraph temporal wide-format files
    if "date" in col_norm and len(columns) > 10 and "supplygraph" in path_lower:
        scores["supplygraph"] = max(scores.get("supplygraph", 0), 0.7)
        signals.setdefault("supplygraph", []).append("temporal wide matrix (Date + node columns)")

    # SupplyGraph edge files
    if {"node1", "node2"}.issubset(col_norm) or ("plant" in col_norm and "node1" in col_norm):
        scores["supplygraph"] = max(scores.get("supplygraph", 0), 0.85)
        signals.setdefault("supplygraph", []).append("edge schema (node1/node2)")

    if not scores:
        return "unknown", 0.0, []

    best = max(scores, key=scores.get)
    return best, round(min(scores[best], 1.0), 3), signals.get(best, [])


def json_safe(value: Any) -> Any:
    """Convert pandas/numpy scalars to JSON-serializable Python types."""
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (ValueError, AttributeError):
            pass
    if isinstance(value, float) and (value != value):  # NaN
        return None
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    return value


def dataframe_profile(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "columns": [],
            "missing_rate": {},
            "dtypes": {},
            "sample_rows": [],
        }

    missing = (df.isna().mean()).round(4).to_dict()
    dtypes = {str(k): str(v) for k, v in df.dtypes.items()}
    raw_sample = df.head(5).where(pd.notna(df.head(5)), None).to_dict(orient="records")
    sample = [json_safe(row) for row in raw_sample]

    return {
        "columns": [str(c) for c in df.columns.tolist()],
        "missing_rate": {str(k): float(v) for k, v in missing.items()},
        "dtypes": dtypes,
        "sample_rows": sample,
    }


def scan_data_files(external_dir: Path) -> list[Path]:
    files: list[Path] = []
    if not external_dir.exists():
        return files
    for path in sorted(external_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in DATA_EXTENSIONS:
            continue
        files.append(path)
    return files


def profile_file(path: Path, external_dir: Path, sample_size: int) -> dict[str, Any]:
    rel = path.relative_to(external_dir)
    df, read_warning = read_tabular_sample(path, sample_size)
    sampled = len(df)
    rows = estimate_row_count(path, df, sampled)
    prof = dataframe_profile(df)
    likely_type, confidence, signals = detect_dataset_type(path, external_dir, prof["columns"])

    return {
        "file_path": str(rel),
        "absolute_path": str(path),
        "file_type": path.suffix.lower().lstrip("."),
        "file_size_bytes": path.stat().st_size,
        "rows": rows,
        "sampled_rows": sampled,
        "sample_size_limit": sample_size,
        "columns": prof["columns"],
        "column_count": len(prof["columns"]),
        "missing_rate": prof["missing_rate"],
        "dtypes": prof["dtypes"],
        "sample_rows": prof["sample_rows"],
        "likely_dataset_type": likely_type,
        "detection_confidence": confidence,
        "detection_signals": signals,
        "read_warning": read_warning,
    }


def summarize_by_dataset(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for ds in KNOWN_DATASETS:
        matched = [p for p in profiles if p["likely_dataset_type"] == ds]
        summary[ds] = {
            "present": bool(matched),
            "file_count": len(matched),
            "total_rows_estimated": sum(p["rows"] or 0 for p in matched),
            "files": [p["file_path"] for p in matched],
        }
    return summary


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# External Dataset Profile Report",
        "",
        f"Generated at: {report['generated_at']}",
        f"External dir: `{report['external_dir']}`",
        f"Sample size limit: {report['sample_size']}",
        "",
        "## Dataset Presence Summary",
        "",
        "| Dataset | Present | Files | Est. Rows |",
        "|---------|---------|-------|-----------|",
    ]

    for ds, info in report["dataset_summary"].items():
        present = "Yes" if info["present"] else "No (skipped in later stages)" 
        lines.append(
            f"| {ds} | {present} | {info['file_count']} | {info['total_rows_estimated']:,} |"
        )

    lines.extend(["", "## Files Scanned", "", f"Total data files: **{report['file_count']}**", ""])

    by_type: dict[str, list[dict[str, Any]]] = {}
    for p in report["files"]:
        by_type.setdefault(p["likely_dataset_type"], []).append(p)

    for ds_type in sorted(by_type.keys()):
        lines.append(f"### {ds_type}")
        lines.append("")
        for p in by_type[ds_type]:
            lines.append(f"#### `{p['file_path']}`")
            lines.append("")
            lines.append(f"- **Type:** {p['file_type']}")
            lines.append(f"- **Size:** {p['file_size_bytes']:,} bytes")
            rows_str = f"{p['rows']:,}" if p["rows"] is not None else "unknown"
            lines.append(f"- **Rows (est.):** {rows_str} (sampled {p['sampled_rows']})")
            lines.append(f"- **Columns ({p['column_count']}):** {', '.join(p['columns'][:20])}")
            if p["column_count"] > 20:
                lines.append(f"  - … and {p['column_count'] - 20} more")
            lines.append(f"- **Detection confidence:** {p['detection_confidence']}")
            if p["detection_signals"]:
                lines.append(f"- **Signals:** {', '.join(p['detection_signals'])}")
            if p["read_warning"]:
                lines.append(f"- **Warning:** {p['read_warning']}")

            # Top missing columns
            miss = sorted(p["missing_rate"].items(), key=lambda x: x[1], reverse=True)
            top_miss = [(c, r) for c, r in miss if r > 0][:8]
            if top_miss:
                lines.append("- **Top missing columns:**")
                for col, rate in top_miss:
                    lines.append(f"  - `{col}`: {rate:.1%}")

            if p["sample_rows"]:
                lines.append("- **Sample rows (first up to 5):**")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(p["sample_rows"], ensure_ascii=False, indent=2)[:4000])
                lines.append("```")
            lines.append("")

    lines.extend(
        [
            "## Recommended Mapping Notes (Phase 1)",
            "",
            "### DataCo (`dataco`)",
            "- Orders, customers, products, deliveries, delivery risk events",
            "- Key fields: Order Id, Product Name, Customer Id, Delivery Status, Late_delivery_risk, Shipping Mode",
            "",
            "### SCMS (`scms`)",
            "- Suppliers, facilities (Manufacturing Site), orders, deliveries, delay risk events",
            "- Key fields: Vendor, Country, Shipment Mode, Scheduled/Delivered dates, Freight Cost",
            "",
            "### SupplyGraph (`supplygraph`)",
            "- Graph nodes (Products/Materials/Plants), edges, temporal flows",
            "- Nodes.csv + Node Types + Edges (Plant/Storage/Product Group) for GraphRAG",
            "- Temporal CSVs are wide time-series matrices (Date × Node)",
            "",
            "### Optional datasets (not found)",
            "",
        ]
    )
    missing = [ds for ds, info in report["dataset_summary"].items() if not info["present"]]
    for ds in missing:
        if ds not in ("dataco", "scms", "supplygraph"):
            lines.append(f"- `{ds}` — directory absent; adapters will no-op")
    lines.append("")
    lines.append("## Next Step")
    lines.append("")
    lines.append("Run `make normalize-data` after adapters are implemented (Phase 2).")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Profile external datasets")
    parser.add_argument(
        "--external-dir",
        type=Path,
        default=ROOT / "data" / "external",
        help="Root directory containing external datasets",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data" / "generated",
        help="Directory for profile reports",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=5000,
        help="Max rows to sample per file for profiling",
    )
    args = parser.parse_args()

    external_dir = args.external_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not external_dir.exists():
        print(f"ERROR: external dir not found: {external_dir}", file=sys.stderr)
        return 1

    files = scan_data_files(external_dir)
    profiles = [profile_file(p, external_dir, args.sample_size) for p in files]

    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "external_dir": str(external_dir),
        "sample_size": args.sample_size,
        "file_count": len(profiles),
        "dataset_summary": summarize_by_dataset(profiles),
        "files": profiles,
    }

    json_path = output_dir / "external_dataset_profile.json"
    md_path = output_dir / "external_dataset_profile.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"Scanned {len(profiles)} data files under {external_dir}")
    for ds in ("dataco", "scms", "supplygraph"):
        info = report["dataset_summary"][ds]
        status = "FOUND" if info["present"] else "MISSING"
        print(f"  [{status}] {ds}: {info['file_count']} files, ~{info['total_rows_estimated']:,} rows")
    optional_missing = [
        ds
        for ds in KNOWN_DATASETS
        if ds not in ("dataco", "scms", "supplygraph") and not report["dataset_summary"][ds]["present"]
    ]
    if optional_missing:
        print(f"  Optional datasets not present (OK): {', '.join(optional_missing)}")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
