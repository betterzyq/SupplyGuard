"""Redis-backed short-term session memory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from packages.common.cache.redis_client import get_redis_client
from packages.common.config import get_settings
from packages.memory.memory_types import SessionMessage

DEFAULT_SESSION_TTL_SECONDS = 86400  # 24h


def _session_key(tenant_id: str, user_id: str, session_id: str) -> str:
    return f"session:{tenant_id}:{user_id}:{session_id}"


async def append_message(
    tenant_id: str,
    user_id: str,
    session_id: str,
    message: SessionMessage,
    *,
    ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
) -> None:
    client = get_redis_client()
    key = _session_key(tenant_id, user_id, session_id)
    payload = json.dumps(message.to_dict(), ensure_ascii=False)
    await client.rpush(key, payload)
    await client.expire(key, ttl_seconds)


async def get_recent_messages(
    tenant_id: str,
    user_id: str,
    session_id: str,
    *,
    limit: int = 20,
) -> list[SessionMessage]:
    client = get_redis_client()
    key = _session_key(tenant_id, user_id, session_id)
    raw_items = await client.lrange(key, -limit, -1)
    messages: list[SessionMessage] = []
    for item in raw_items:
        try:
            messages.append(SessionMessage.from_dict(json.loads(item)))
        except (json.JSONDecodeError, TypeError):
            continue
    return messages


async def get_recent_entities(
    tenant_id: str,
    user_id: str,
    session_id: str,
    *,
    limit: int = 10,
) -> dict[str, str]:
    entities: dict[str, str] = {}
    for message in reversed(await get_recent_messages(tenant_id, user_id, session_id, limit=limit)):
        for key, value in message.entities.items():
            if key not in entities and value:
                entities[key] = value
    return entities


async def clear_session(tenant_id: str, user_id: str, session_id: str) -> None:
    client = get_redis_client()
    await client.delete(_session_key(tenant_id, user_id, session_id))


async def summarize_if_too_long(
    tenant_id: str,
    user_id: str,
    session_id: str,
    *,
    max_messages: int = 50,
) -> dict[str, Any]:
    """Reserved hook — returns stats only in MVP memory phase."""
    client = get_redis_client()
    key = _session_key(tenant_id, user_id, session_id)
    length = await client.llen(key)
    return {
        "message_count": length,
        "needs_summary": length > max_messages,
        "summarized": False,
    }


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
