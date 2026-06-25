"""Qdrant client and health check."""

from typing import Any

from qdrant_client import AsyncQdrantClient

from packages.common.config import Settings, get_settings

_client: AsyncQdrantClient | None = None


def get_qdrant_client(settings: Settings | None = None) -> AsyncQdrantClient:
    global _client
    if _client is None:
        settings = settings or get_settings()
        _client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            timeout=settings.QDRANT_TIMEOUT_SECONDS,
            check_compatibility=False,
        )
    return _client


async def check_qdrant_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        client = get_qdrant_client(settings)
        await client.get_collections()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


async def close_qdrant() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
