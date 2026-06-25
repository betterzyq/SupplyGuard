"""Health check endpoints."""

import asyncio

from fastapi import APIRouter

from packages.common.cache.redis_client import check_redis_health
from packages.common.config import get_settings
from packages.common.db.session import check_postgres_health
from packages.common.embedding.openai_compatible import check_embedding_health
from packages.common.graph.neo4j_client import check_neo4j_health
from packages.common.llm.factory import check_llm_health
from packages.common.storage.minio_client import check_minio_health
from packages.common.vector.qdrant_client import check_qdrant_health

router = APIRouter(tags=["health"])

HEALTH_CHECK_TIMEOUT_SECONDS = 10.0


async def _run_with_timeout(name: str, coro) -> dict:
    try:
        return await asyncio.wait_for(coro, timeout=HEALTH_CHECK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        return {"status": "error", "message": f"{name} health check timed out"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "SupplyGuard",
        "version": "0.1.0",
    }


@router.get("/health/dependencies")
async def health_dependencies() -> dict:
    settings = get_settings()

    names = [
        "postgres",
        "redis",
        "qdrant",
        "neo4j",
        "minio",
        "llm",
        "embedding",
    ]
    coros = [
        check_postgres_health(settings),
        check_redis_health(settings),
        check_qdrant_health(settings),
        check_neo4j_health(settings),
        check_minio_health(settings),
        check_llm_health(settings),
        check_embedding_health(settings),
    ]

    results = await asyncio.gather(
        *[_run_with_timeout(name, coro) for name, coro in zip(names, coros)]
    )

    dependencies = dict(zip(names, results))

    overall = "ok"
    if any(item.get("status") != "ok" for item in dependencies.values()):
        overall = "degraded"

    return {
        "status": overall,
        "dependencies": dependencies,
    }
