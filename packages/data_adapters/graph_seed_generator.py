"""Placeholder for graph seed JSON generation (Phase 3+)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def export_graph_seed_preview(normalized_dir: Path, output_path: Path) -> dict:
    """Write lightweight graph seed preview from normalized edges."""
    normalized_dir = Path(normalized_dir)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {}
    for name in ["materials", "products", "supplier_material_edges", "material_product_edges"]:
        path = normalized_dir / f"{name}.csv"
        stats[name] = len(pd.read_csv(path)) if path.exists() else 0

    preview = {"source": "normalized", "stats": stats}
    output_path.write_text(__import__("json").dumps(preview, indent=2), encoding="utf-8")
    return preview
