"""Quality checks for normalized real-data pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from packages.data_adapters.schema import NORMALIZED_TABLE_NAMES


@dataclass
class PipelineQualityReport:
    passed: bool = True
    checks: list[dict] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            self.passed = False


NORMALIZED_OPTIONAL_EMPTY_TABLES = frozenset(
    {"quality_issues", "country_risk_scores", "compliance_entities"}
)


def validate_normalized_dir(normalized_dir: Path) -> PipelineQualityReport:
    report = PipelineQualityReport()
    normalized_dir = Path(normalized_dir)

    for name in NORMALIZED_TABLE_NAMES:
        path = normalized_dir / f"{name}.csv"
        ok = path.exists()
        if not ok and name in NORMALIZED_OPTIONAL_EMPTY_TABLES:
            ok = True
            detail = f"{path} optional empty (OK)"
        else:
            detail = f"{path} {'exists' if ok else 'missing'}"
        report.add(f"file:{name}", ok, detail)

    def count_table(name: str) -> int:
        path = normalized_dir / f"{name}.csv"
        if not path.exists():
            return 0
        return len(pd.read_csv(path, low_memory=False))

    report.add("suppliers>0", count_table("suppliers") > 0, f"suppliers={count_table('suppliers')}")
    report.add("orders>0", count_table("orders") > 0, f"orders={count_table('orders')}")
    report.add("deliveries>0", count_table("deliveries") > 0, f"deliveries={count_table('deliveries')}")
    report.add("risk_events>0", count_table("risk_events") > 0, f"risk_events={count_table('risk_events')}")
    report.add(
        "graph_edges>0",
        count_table("material_product_edges") > 0 or count_table("supplier_material_edges") > 0,
        f"mp={count_table('material_product_edges')} sm={count_table('supplier_material_edges')}",
    )

    return report
