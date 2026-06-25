"""Neo4j driver and health check."""

from typing import Any

from neo4j import AsyncGraphDatabase, AsyncDriver

from packages.common.config import Settings, get_settings

_driver: AsyncDriver | None = None


def get_neo4j_driver(settings: Settings | None = None) -> AsyncDriver:
    global _driver
    if _driver is None:
        settings = settings or get_settings()
        _driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=5,
        )
    return _driver


async def check_neo4j_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        driver = get_neo4j_driver(settings)
        await driver.verify_connectivity()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def close_neo4j() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
