#!/usr/bin/env python3
"""CLI entrypoint for SupplyGuard benchmarks."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from packages.benchmarks.benchmark_runner import BenchmarkConfig, load_admin_context, run_benchmark  # noqa: E402
from packages.common.db.session import get_session_factory  # noqa: E402
from packages.observability.trace_context import resolve_trace_id, set_trace_id  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SupplyGuard benchmark")
    parser.add_argument("--name", default="cli_benchmark")
    parser.add_argument("--mode", default="secure_rag", choices=[
        "naive_rag",
        "secure_rag",
        "hybrid_rag",
        "secure_rag_memory",
        "hybrid_rag_memory",
        "graphrag",
        "memory",
        "permission",
        "all",
    ])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--chunk-size", type=int, default=512)
    parser.add_argument("--permission-filter", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--memory", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-export", action="store_true")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    config = BenchmarkConfig(
        name=args.name,
        mode=args.mode,
        limit=args.limit,
        dry_run=args.dry_run,
        top_k=args.top_k,
        chunk_size=args.chunk_size,
        permission_filter=args.permission_filter,
        memory=args.memory,
        export_reports=not args.no_export,
    )
    session_factory = get_session_factory()
    set_trace_id(resolve_trace_id())
    async with session_factory() as session:
        admin = await load_admin_context(session)
        result = await run_benchmark(session, admin_context=admin, config=config)
        await session.commit()
    print("__BENCHMARK_RESULT__")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
