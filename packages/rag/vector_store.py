"""Qdrant vector store operations."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels
from tenacity import retry, stop_after_attempt, wait_exponential

from packages.common.config import Settings, get_settings
from packages.common.db.models.document import Document, DocumentChunk
from packages.common.vector.qdrant_client import get_qdrant_client

_collection_ready = False

_QDRANT_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


def chunk_payload(document: Document, chunk: DocumentChunk) -> dict[str, Any]:
    return {
        "tenant_id": str(document.tenant_id),
        "document_id": str(document.id),
        "chunk_id": str(chunk.id),
        "chunk_index": chunk.chunk_index,
        "doc_type": document.doc_type,
        "title": document.title,
        "source_uri": document.source_uri,
        "file_name": document.file_name,
        "security_level": chunk.security_level,
        "security_level_rank": chunk.security_level_rank,
        "access_scope": chunk.access_scope,
        "department": chunk.department,
        "allowed_roles": chunk.allowed_roles or [],
        "allowed_users": [str(item) for item in (chunk.allowed_users or [])],
        "supplier_id": str(chunk.supplier_id) if chunk.supplier_id else None,
        "token_count": chunk.token_count,
    }


@_QDRANT_RETRY
async def _collection_exists(
    client: AsyncQdrantClient,
    settings: Settings,
) -> bool:
    collections = await client.get_collections()
    return settings.QDRANT_COLLECTION in {item.name for item in collections.collections}


@_QDRANT_RETRY
async def ensure_collection(
    client: AsyncQdrantClient | None = None,
    settings: Settings | None = None,
) -> None:
    global _collection_ready
    if _collection_ready:
        return

    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    if await _collection_exists(client, settings):
        _collection_ready = True
        return

    await client.create_collection(
        collection_name=settings.QDRANT_COLLECTION,
        vectors_config=qmodels.VectorParams(
            size=settings.EMBEDDING_DIM,
            distance=qmodels.Distance.COSINE,
        ),
    )
    _collection_ready = True


@_QDRANT_RETRY
async def upsert_chunks(
    document: Document,
    chunks: list[DocumentChunk],
    vectors: list[list[float]],
    *,
    client: AsyncQdrantClient | None = None,
    settings: Settings | None = None,
) -> None:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")
    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    await ensure_collection(client, settings)

    points = [
        qmodels.PointStruct(
            id=str(chunk.id),
            vector=vector,
            payload=chunk_payload(document, chunk),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)


@_QDRANT_RETRY
async def delete_document_points(
    document_id: uuid.UUID,
    *,
    client: AsyncQdrantClient | None = None,
    settings: Settings | None = None,
) -> None:
    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    if not await _collection_exists(client, settings):
        return
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=qmodels.FilterSelector(
            filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="document_id",
                        match=qmodels.MatchValue(value=str(document_id)),
                    )
                ]
            )
        ),
    )


@_QDRANT_RETRY
async def search_vectors(
    query_vector: list[float],
    *,
    permission_filter: qmodels.Filter,
    top_k: int = 5,
    client: AsyncQdrantClient | None = None,
    settings: Settings | None = None,
) -> list[qmodels.ScoredPoint]:
    settings = settings or get_settings()
    client = client or get_qdrant_client(settings)
    await ensure_collection(client, settings)
    response = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_vector,
        query_filter=permission_filter,
        limit=top_k,
        with_payload=True,
    )
    return list(response.points or [])
