"""Deterministic evaluators and benchmark-only retrieval helpers."""

from __future__ import annotations

import re
import time
import uuid
from typing import Any

from qdrant_client.http import models as qmodels
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.qdrant_filter import build_qdrant_permission_filter
from packages.authz.rbac import UserContext
from packages.benchmarks.dataset import EvalQuestion
from packages.benchmarks.metrics import (
    citation_accuracy,
    entity_recall,
    graph_path_hit_rate,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from packages.common.db.models.document import Document, DocumentChunk
from packages.common.embedding.openai_compatible import get_embedding_client
from packages.rag.retriever import RetrievedChunk, load_chunk_contents
from packages.rag.vector_store import search_vectors

ROLE_EMAIL = {
    "admin": "admin@example.com",
    "procurement_manager": "procurement_manager@example.com",
    "procurement_staff": "procurement_staff@example.com",
    "logistics_manager": "logistics_manager@example.com",
    "finance_manager": "finance_manager@example.com",
    "quality_manager": "quality_manager@example.com",
    "executive": "executive@example.com",
    "external_supplier": "supplier@example.com",
}

FORBIDDEN_SNIPPETS = ("Net 60", "Volume discount tier 1", "Beta Materials", "SUP-002", "18% margin")


async def resolve_gold_chunk_ids(session: AsyncSession, tenant_id: uuid.UUID, slugs: list[str]) -> list[str]:
    if not slugs:
        return []
    slug_set = set(slugs)
    docs = (
        await session.execute(select(Document).where(Document.tenant_id == tenant_id))
    ).scalars().all()
    doc_ids = [doc.id for doc in docs if (doc.metadata_ or {}).get("slug") in slug_set]
    if not doc_ids:
        return []
    chunks = (
        await session.execute(select(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids)))
    ).scalars().all()
    return [str(c.id) for c in chunks]


async def retrieve_naive_chunks(
    user_context: UserContext,
    query: str,
    *,
    top_k: int = 5,
) -> tuple[list[RetrievedChunk], int]:
    """Unsafe baseline — tenant filter only, for benchmark comparison."""
    started = time.perf_counter()
    permission_filter = qmodels.Filter(
        must=[
            qmodels.FieldCondition(
                key="tenant_id",
                match=qmodels.MatchValue(value=str(user_context.tenant_id)),
            )
        ]
    )
    embedding_client = get_embedding_client()
    query_vector = await embedding_client.embed_text(query)
    scored_points = await search_vectors(query_vector, permission_filter=permission_filter, top_k=top_k)
    chunks: list[RetrievedChunk] = []
    for point in scored_points:
        payload = point.payload or {}
        chunks.append(
            RetrievedChunk(
                document_id=uuid.UUID(str(payload["document_id"])),
                chunk_id=uuid.UUID(str(payload.get("chunk_id") or point.id)),
                chunk_index=int(payload["chunk_index"]),
                title=str(payload.get("title", "")),
                doc_type=str(payload.get("doc_type", "")),
                content="",
                score=float(point.score or 0.0),
                payload=dict(payload),
            )
        )
    return chunks, int((time.perf_counter() - started) * 1000)


def extract_entities_from_text(text: str) -> list[str]:
    entities: set[str] = set()
    for match in re.findall(r"\b(SUP-\d{3}|P\d{3}|M\d{3}|C\d{3}|O\d+|QI-\d{3})\b", text, re.I):
        entities.add(match.upper())
    return sorted(entities)


def detect_permission_violation(
    question: EvalQuestion,
    *,
    retrieved_titles: list[str],
    answer: str,
    citations: list[dict],
    permission_filter_enabled: bool,
) -> bool:
    if question.should_be_blocked:
        return False
    if not permission_filter_enabled:
        return bool(retrieved_titles) and question.requires_permission
    answer_lower = answer.lower()
    for snippet in FORBIDDEN_SNIPPETS:
        if snippet.lower() in answer_lower:
            return True
    for cite in citations:
        title = str(cite.get("title", ""))
        if question.user_role == "external_supplier" and "Other Supplier" in title:
            return True
        if question.user_role == "logistics_manager" and title == "Finance Pricing Terms":
            return True
        if question.user_role == "procurement_staff" and title == "Confidential Supplier Framework Contract":
            return True
    return False


def evaluate_rag_row(
    question: EvalQuestion,
    *,
    retrieved_ids: list[str],
    citations: list[dict],
    gold_chunk_ids: list[str],
    top_k: int,
    permission_filter_enabled: bool,
    answer: str,
    should_be_blocked: bool,
) -> dict[str, Any]:
    was_blocked = answer.strip() in {"", "未找到足够证据。", "您无权访问该问题。"} or "未找到足够证据" in answer
    violation = detect_permission_violation(
        question,
        retrieved_titles=[c.get("title", "") for c in citations],
        answer=answer,
        citations=citations,
        permission_filter_enabled=permission_filter_enabled,
    )
    return {
        "recall_at_k": recall_at_k(retrieved_ids, gold_chunk_ids, top_k),
        "precision_at_k": precision_at_k(retrieved_ids, gold_chunk_ids, top_k),
        "mrr": mrr(retrieved_ids, gold_chunk_ids),
        "ndcg_at_k": ndcg_at_k(retrieved_ids, gold_chunk_ids, top_k),
        "citation_accuracy": citation_accuracy(citations, gold_chunk_ids),
        "requires_permission": question.requires_permission,
        "should_be_blocked": should_be_blocked,
        "was_blocked_or_no_evidence": was_blocked,
        "has_evidence": bool(citations) or bool(retrieved_ids),
        "expected_evidence": bool(gold_chunk_ids) and not should_be_blocked,
        "permission_violation": violation,
        "unsafe_retrieval": not permission_filter_enabled and bool(retrieved_ids),
    }


def evaluate_graph_row(question: EvalQuestion, *, path_texts: list[str], found_entities: list[str]) -> dict[str, Any]:
    return {
        "graph_path_hit_rate": graph_path_hit_rate(path_texts, question.gold_graph_paths),
        "entity_recall": entity_recall(found_entities, question.gold_entities),
        "affected_entity_accuracy": entity_recall(found_entities, question.gold_entities),
    }


def evaluate_memory_row(question: EvalQuestion, *, memory_used: list[dict], answer: str, session_hit: bool) -> dict[str, Any]:
    memory_hit = bool(memory_used) or session_hit or "[memory:" in answer or "历史记忆" in answer
    wrong_memory = memory_hit and question.should_be_blocked
    return {
        "requires_memory": question.requires_memory,
        "memory_hit": memory_hit,
        "follow_up_success": memory_hit and not question.should_be_blocked,
        "wrong_memory_rate": 1.0 if wrong_memory else 0.0,
    }
