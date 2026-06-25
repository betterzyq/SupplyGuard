"""MinIO client (interface reserved) and health check."""

from typing import Any

import urllib3
from minio import Minio

from packages.common.config import Settings, get_settings

_client: Minio | None = None


def get_minio_client(settings: Settings | None = None) -> Minio:
    global _client
    if _client is None:
        settings = settings or get_settings()
        http_client = urllib3.PoolManager(
            timeout=urllib3.util.Timeout(connect=5.0, read=10.0),
            cert_reqs="CERT_REQUIRED" if settings.MINIO_SECURE else "CERT_NONE",
        )
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
            http_client=http_client,
        )
    return _client


async def check_minio_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    try:
        client = get_minio_client(settings)
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)
        client.list_buckets()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
