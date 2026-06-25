"""Secure RAG answer generation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from packages.authz.audit import write_audit_log
from packages.authz.rbac import UserContext
from packages.common.llm.factory import get_llm_client
from packages.observability.repositories.retrieval_log_repo import write_retrieval_log
from packages.rag.citations import Citation, build_evidence_block, format_citation_marker
from packages.rag.prompts import (
    NO_EVIDENCE_ANSWER,
    NO_PERMISSION_ANSWER,
    RAG_SYSTEM_PROMPT,
    build_rag_user_prompt,
)
from packages.rag.retriever import (
    RetrievedChunk,
    load_chunk_contents,
    retrieve_authorized_chunks,
)


@dataclass
class SecureRAGResult:
    query: str
    answer: str
    citations: list[Citation]
    trace_id: str
    status: str
    retrieval: dict[str, Any]
    token_usage: dict[str, Any]


def _build_citations(chunks: list[RetrievedChunk]) -> list[Citation]:
    return [
        Citation(
            document_id=item.document_id,
            chunk_id=item.chunk_id,
            chunk_index=item.chunk_index,
            title=item.title,
            score=item.score,
            snippet=item.snippet,
        )
        for item in chunks
    ]


async def run_secure_rag_query(
    session: AsyncSession,
    user_context: UserContext,
    query: str,
    *,
    trace_id: str,
    top_k: int = 5,
    chunk_size_config: int = 512,
    doc_type: str | None = None,
    supplier_id: uuid.UUID | None = None,
    department: str | None = None,
    agent_run_id: uuid.UUID | None = None,
    ip_address: str | None = None,
) -> SecureRAGResult:
    chunks, filter_applied, latency_ms = await retrieve_authorized_chunks(
        user_context,
        query,
        top_k=top_k,
        chunk_size_config=chunk_size_config,
        doc_type=doc_type,
        supplier_id=supplier_id,
        department=department,
    )
    chunks = await load_chunk_contents(session, chunks)

    results_payload = [
        {
            "document_id": str(item.document_id),
            "chunk_id": str(item.chunk_id),
            "chunk_index": item.chunk_index,
            "score": item.score,
            "title": item.title,
        }
        for item in chunks
    ]

    await write_retrieval_log(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        query=query,
        filter_applied=filter_applied,
        top_k=top_k,
        chunk_size_config=chunk_size_config,
        results=results_payload,
        latency_ms=latency_ms,
        result_count=len(chunks),
        agent_run_id=agent_run_id,
    )

    retrieval_meta = {
        "top_k": top_k,
        "result_count": len(chunks),
        "filter_applied": filter_applied,
        "latency_ms": latency_ms,
    }

    if not chunks:
        await write_audit_log(
            session,
            tenant_id=user_context.tenant_id,
            user_id=user_context.user_id,
            trace_id=trace_id,
            action="rag_query_no_evidence",
            resource_type="rag",
            resource_id=trace_id,
            permission_decision="allowed",
            reason="no authorized chunks retrieved",
            ip_address=ip_address,
            metadata={"query": query},
        )
        return SecureRAGResult(
            query=query,
            answer=NO_EVIDENCE_ANSWER,
            citations=[],
            trace_id=trace_id,
            status="no_evidence",
            retrieval=retrieval_meta,
            token_usage={},
        )

    await write_audit_log(
        session,
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        trace_id=trace_id,
        action="rag_query_allowed",
        resource_type="rag",
        resource_id=trace_id,
        permission_decision="allowed",
        reason=f"retrieved {len(chunks)} authorized chunks",
        ip_address=ip_address,
        metadata={"query": query},
    )

    evidence = [item.to_evidence_dict() for item in chunks]
    evidence_block = build_evidence_block(evidence)
    llm = get_llm_client()
    chat_result = await llm.chat(
        [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": build_rag_user_prompt(query, evidence_block)},
        ]
    )

    citations = _build_citations(chunks)
    answer = chat_result.content.strip()
    if not answer:
        answer = NO_EVIDENCE_ANSWER

    if "证据来源" not in answer:
        markers = ", ".join(
            format_citation_marker(item.document_id, item.chunk_index) for item in chunks[:3]
        )
        answer = f"{answer}\n\n证据来源：{markers}"

    return SecureRAGResult(
        query=query,
        answer=answer,
        citations=citations,
        trace_id=trace_id,
        status="answered",
        retrieval=retrieval_meta,
        token_usage=chat_result.token_usage,
    )


def build_no_permission_result(query: str, trace_id: str) -> SecureRAGResult:
    return SecureRAGResult(
        query=query,
        answer=NO_PERMISSION_ANSWER,
        citations=[],
        trace_id=trace_id,
        status="blocked",
        retrieval={"top_k": 0, "result_count": 0, "filter_applied": {}},
        token_usage={},
    )
