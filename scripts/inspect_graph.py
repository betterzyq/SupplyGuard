#!/usr/bin/env python3
"""Inspect Neo4j supply graph stats."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.graphrag.graph_builder import count_graph_stats
from packages.graphrag.neo4j_client import run_cypher


async def inspect() -> None:
    rows = await run_cypher(
        """
        MATCH (n)
        WHERE n.tenant_id IS NOT NULL
        RETURN DISTINCT n.tenant_id AS tenant_id
        LIMIT 5
        """
    )
    if not rows:
        print("No graph data found.")
        return

    tenant_id = rows[0]["tenant_id"]
    stats = await count_graph_stats(tenant_id)
    print(f"tenant_id={tenant_id}")
    for key, value in stats.items():
        print(f"  {key}: {value}")

    sample = await run_cypher(
        """
        MATCH path = (s:Supplier)-[:SUPPLIES]->(:Material)-[:USED_IN]->(:Product)
        WHERE s.tenant_id = $tenant_id
        RETURN path
        LIMIT 3
        """,
        {"tenant_id": tenant_id},
    )
    print(f"sample_supply_paths: {len(sample)}")


def main() -> None:
    asyncio.run(inspect())


if __name__ == "__main__":
    main()
