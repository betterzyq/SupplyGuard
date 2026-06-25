"""Redis client and health check."""

from typing import Any

import redis.asyncio as aioredis

from packages.common.config import Settings, get_settings

_client: aioredis.Redis | None = None


def get_redis_client(settings: Settings | None = None) -> aioredis.Redis:
    global _client
    if _client is None:
        settings = settings or get_settings()
        _client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _client


async def check_redis_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        client = get_redis_client(settings)
        pong = await client.ping()
        if pong:
            return {"status": "ok"}
        return {"status": "error", "message": "Redis ping returned falsy response"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def close_redis() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
