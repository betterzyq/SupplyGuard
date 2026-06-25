"""Secure vector retriever."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client.http import models as qmodels

from packages.authz.qdrant_filter import build_qdrant_permission_filter
from packages.authz.rbac import UserContext
from packages.common.embedding.openai_compatible import get_embedding_client
from packages.rag.vector_store import search_vectors


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_index: int
    title: str
    doc_type: str
    content: str
    score: float
    payload: dict[str, Any]

    @property
    def snippet(self) -> str:
        text = self.content.strip()
        return text[:280] + ("..." if len(text) > 280 else "")

    def to_evidence_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "chunk_index": self.chunk_index,
            "title": self.title,
            "content": self.content,
            "score": self.score,
            "doc_type": self.doc_type,
        }


def filter_to_dict(filter_obj: qmodels.Filter) -> dict[str, Any]:
    return filter_obj.model_dump(exclude_none=True)


async def retrieve_authorized_chunks(
    user_context: UserContext,
    query: str,
    *,
    top_k: int = 5,
    chunk_size_config: int = 512,
    doc_type: str | None = None,
    supplier_id: uuid.UUID | None = None,
    department: str | None = None,
) -> tuple[list[RetrievedChunk], dict[str, Any], int]:
    extra: dict[str, Any] = {}
    if doc_type:
        extra["doc_type"] = doc_type
    if supplier_id:
        extra["supplier_id"] = str(supplier_id)
    if department:
        extra["department"] = department

    if user_context.is_external_supplier and user_context.supplier_id:
        extra["supplier_id"] = str(user_context.supplier_id)

    permission_filter = build_qdrant_permission_filter(user_context, extra_filters=extra or None)
    filter_applied = filter_to_dict(permission_filter)

    started = time.perf_counter()
    embedding_client = get_embedding_client()
    query_vector = await embedding_client.embed_text(query)
    scored_points = await search_vectors(
        query_vector,
        permission_filter=permission_filter,
        top_k=top_k,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)

    chunks: list[RetrievedChunk] = []
    for point in scored_points:
        payload = point.payload or {}
        chunk_id = uuid.UUID(str(payload.get("chunk_id") or point.id))
        chunks.append(
            RetrievedChunk(
                document_id=uuid.UUID(str(payload["document_id"])),
                chunk_id=chunk_id,
                chunk_index=int(payload["chunk_index"]),
                title=str(payload.get("title", "")),
                doc_type=str(payload.get("doc_type", "")),
                content="",
                score=float(point.score or 0.0),
                payload=dict(payload),
            )
        )

    return chunks, filter_applied, latency_ms


async def load_chunk_contents(
    session,
    chunks: list[RetrievedChunk],
) -> list[RetrievedChunk]:
    if not chunks:
        return chunks

    from sqlalchemy import select

    from packages.common.db.models.document import DocumentChunk

    chunk_ids = [item.chunk_id for item in chunks]
    rows = (
        await session.execute(select(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids)))
    ).scalars().all()
    content_by_id = {row.id: row.content for row in rows}

    enriched: list[RetrievedChunk] = []
    for item in chunks:
        enriched.append(
            RetrievedChunk(
                document_id=item.document_id,
                chunk_id=item.chunk_id,
                chunk_index=item.chunk_index,
                title=item.title,
                doc_type=item.doc_type,
                content=content_by_id.get(item.chunk_id, ""),
                score=item.score,
                payload=item.payload,
            )
        )
    return enriched
