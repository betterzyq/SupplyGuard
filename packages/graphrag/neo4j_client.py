"""Neo4j query helpers for GraphRAG."""

from __future__ import annotations

from typing import Any

from packages.common.graph.neo4j_client import get_neo4j_driver


async def run_cypher(
    query: str,
    parameters: dict[str, Any] | None = None,
    *,
    database: str | None = None,
) -> list[dict[str, Any]]:
    driver = get_neo4j_driver()
    params = parameters or {}
    async with driver.session(database=database) as session:
        result = await session.run(query, params)
        rows: list[dict[str, Any]] = []
        async for record in result:
            rows.append({key: record[key] for key in record.keys()})
        return rows


async def run_write(query: str, parameters: dict[str, Any] | None = None) -> None:
    driver = get_neo4j_driver()
    params = parameters or {}
    async with driver.session() as session:
        await session.run(query, params)
