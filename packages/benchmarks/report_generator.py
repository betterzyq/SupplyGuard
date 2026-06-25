"""Benchmark report export (JSON / CSV / Markdown)."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.common.db.models.benchmark import BenchmarkResult, BenchmarkRun


def reports_dir() -> Path:
    path = Path(__file__).resolve().parents[2] / "data" / "eval" / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def export_reports(run: BenchmarkRun, results: list[BenchmarkResult], summary: dict[str, Any]) -> dict[str, str]:
    base = reports_dir() / str(run.id)
    json_path = base.with_suffix(".json")
    csv_path = base.with_suffix(".csv")
    md_path = base.with_suffix(".md")

    payload = {
        "benchmark_run_id": str(run.id),
        "name": run.name,
        "mode": run.mode,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "config": run.config,
        "summary": summary,
        "results": [
            {
                "question_id": item.question_id,
                "question_type": item.question_type,
                "question": item.question,
                "metrics": item.metrics,
                "latency_ms": item.latency_ms,
                "error": item.error,
            }
            for item in results
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "question_id",
                "question_type",
                "latency_ms",
                "recall_at_k",
                "precision_at_k",
                "citation_accuracy",
                "graph_path_hit_rate",
                "entity_recall",
                "permission_violation",
                "memory_hit",
                "error",
            ],
        )
        writer.writeheader()
        for item in results:
            metrics = item.metrics or {}
            writer.writerow(
                {
                    "question_id": item.question_id,
                    "question_type": item.question_type,
                    "latency_ms": item.latency_ms,
                    "recall_at_k": metrics.get("recall_at_k"),
                    "precision_at_k": metrics.get("precision_at_k"),
                    "citation_accuracy": metrics.get("citation_accuracy"),
                    "graph_path_hit_rate": metrics.get("graph_path_hit_rate"),
                    "entity_recall": metrics.get("entity_recall"),
                    "permission_violation": metrics.get("permission_violation"),
                    "memory_hit": metrics.get("memory_hit"),
                    "error": item.error,
                }
            )

    md_path.write_text(_render_markdown(run, results, summary), encoding="utf-8")
    return {"json": str(json_path), "csv": str(csv_path), "markdown": str(md_path)}


def _render_markdown(run: BenchmarkRun, results: list[BenchmarkResult], summary: dict[str, Any]) -> str:
    by_type = summary.get("by_question_type") or {}
    failures = [item for item in results if item.error or (item.metrics or {}).get("failure")]
    failures = sorted(failures, key=lambda x: x.question_id)[:10]

    lines = [
        f"# Benchmark Report: {run.name}",
        "",
        f"- **Run ID**: `{run.id}`",
        f"- **Mode**: {run.mode}",
        f"- **Status**: {run.status}",
        f"- **Started**: {run.started_at}",
        f"- **Completed**: {run.completed_at or datetime.now(UTC).isoformat()}",
        f"- **Dataset size**: {len(results)}",
        "",
        "## Parameters",
        "",
        "```json",
        json.dumps(run.config, ensure_ascii=False, indent=2),
        "```",
        "",
        "## Overall Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key in [
        "recall_at_k",
        "precision_at_k",
        "mrr",
        "ndcg_at_k",
        "citation_accuracy",
        "graph_path_hit_rate",
        "entity_recall",
        "permission_violation_rate",
        "blocked_accuracy",
        "allowed_accuracy",
        "memory_hit_rate",
        "latency_ms",
        "p95_latency_ms",
        "failure_rate",
        "unsafe_retrieval_count",
    ]:
        if key in summary and summary[key] is not None:
            lines.append(f"| {key} | {summary[key]} |")

    lines.extend(["", "## Metrics by Question Type", ""])
    for qtype, metrics in sorted(by_type.items()):
        lines.append(f"### {qtype}")
        lines.append("")
        for key, value in metrics.items():
            if key not in {"count", "by_question_type"}:
                lines.append(f"- {key}: {value}")
        lines.append("")

    perm_rows = [r for r in results if r.question_type in {"permission_boundary", "external_supplier"}]
    if perm_rows:
        lines.extend(["## Permission Test Results", ""])
        for row in perm_rows:
            metrics = row.metrics or {}
            lines.append(
                f"- `{row.question_id}`: blocked={metrics.get('was_blocked_or_no_evidence')} "
                f"violation={metrics.get('permission_violation')}"
            )
        lines.append("")

    graph_rows = [r for r in results if r.question_type == "graphrag" or (r.metrics or {}).get("graph_path_hit_rate") is not None]
    if graph_rows:
        lines.extend(["## GraphRAG Path Hits", ""])
        for row in graph_rows[:15]:
            hit = (row.metrics or {}).get("graph_path_hit_rate", 0)
            lines.append(f"- `{row.question_id}`: path_hit_rate={hit}")
        lines.append("")

    mem_rows = [r for r in results if r.question_type == "memory_followup"]
    if mem_rows:
        lines.extend(["## Memory Follow-up Results", ""])
        for row in mem_rows:
            hit = (row.metrics or {}).get("memory_hit", False)
            lines.append(f"- `{row.question_id}`: memory_hit={hit}")
        lines.append("")

    lines.extend(["## Top Failure Samples", ""])
    if not failures:
        lines.append("_No failures recorded._")
    else:
        for row in failures:
            lines.append(f"- `{row.question_id}` ({row.question_type}): {row.error or row.metrics}")

    lines.extend(
        [
            "",
            "## Recommendations",
            "",
            "- Review permission boundary cases with false allows or false blocks.",
            "- Tune top_k / chunk_size for retrieval metrics below target.",
            "- Expand GraphRAG gold paths for multi-hop supplier impact questions.",
            "- Seed short-term memory context for follow-up questions with low memory_hit_rate.",
            "- LLM-as-judge (faithfulness / answer relevance) is not enabled in Stage A.",
        ]
    )
    return "\n".join(lines) + "\n"
