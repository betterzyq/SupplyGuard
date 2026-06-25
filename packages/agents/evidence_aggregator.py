"""Merge RAG, GraphRAG, and Memory evidence."""

from __future__ import annotations

from typing import Any

from packages.agents.context_budget_manager import apply_context_budget
from packages.agents.evidence_types import EvidenceItem
from packages.agents.prompt_compressor import compress_evidence_content
from packages.graphrag.graph_context import GraphPath
from packages.rag.retriever import RetrievedChunk


def _dedupe_key(item: EvidenceItem) -> str:
    return f"{item.evidence_type}:{item.source_id}:{item.citation or ''}"


def evidence_from_rag_chunks(chunks: list[RetrievedChunk]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for chunk in chunks:
        citation = f"[doc:{chunk.document_id}#chunk:{chunk.chunk_index}]"
        items.append(
            EvidenceItem(
                evidence_id=str(chunk.chunk_id),
                evidence_type="rag_chunk",
                source_id=str(chunk.document_id),
                source_title=chunk.title,
                content=chunk.content,
                score=chunk.score,
                confidence=min(chunk.score + 0.2, 1.0),
                permission_scope="authorized_rag",
                citation=citation,
                metadata={"chunk_index": chunk.chunk_index, "doc_type": chunk.doc_type},
            )
        )
    return items


def evidence_from_graph_paths(paths: list[GraphPath]) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for path in paths:
        citation = f"[graph:{path.template_id}#path:{path.path_index}]"
        items.append(
            EvidenceItem(
                evidence_id=f"{path.template_id}#path_{path.path_index}",
                evidence_type="graph_path",
                source_id=path.template_id,
                source_title=f"Graph path {path.path_index}",
                content=path.path_text,
                score=0.9,
                confidence=0.95,
                permission_scope="graph",
                citation=citation,
                metadata={"path_index": path.path_index},
            )
        )
    return items


def evidence_from_memory_items(memory_evidence: list[dict[str, Any]]) -> list[EvidenceItem]:
    return [EvidenceItem.from_dict(item) for item in memory_evidence]


def evidence_from_tool_items(tool_evidence: list[dict[str, Any]]) -> list[EvidenceItem]:
    return [EvidenceItem.from_dict(item) for item in tool_evidence]


def aggregate_evidence(
    *,
    rag_chunks: list[RetrievedChunk] | None = None,
    graph_paths: list[GraphPath] | None = None,
    memory_evidence: list[dict[str, Any]] | None = None,
    tool_evidence: list[dict[str, Any]] | None = None,
    max_context_tokens: int = 8000,
) -> tuple[list[EvidenceItem], dict[str, Any]]:
    rag_items = evidence_from_rag_chunks(rag_chunks or [])
    graph_items = evidence_from_graph_paths(graph_paths or [])
    memory_items = evidence_from_memory_items(memory_evidence or [])
    tool_items = evidence_from_tool_items(tool_evidence or [])

    combined: list[EvidenceItem] = []
    seen: set[str] = set()
    for bucket in (tool_items, rag_items, graph_items, memory_items):
        for item in bucket:
            key = _dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            combined.append(item)

    type_priority = {"tool_result": 0, "rag_chunk": 1, "graph_path": 2, "memory": 3}
    combined.sort(
        key=lambda item: (
            type_priority.get(item.evidence_type, 9),
            -item.score,
            -item.confidence,
        )
    )

    # Session turns are context hints only — keep for entity resolution, drop from prompt budget.
    combined = [
        item
        for item in combined
        if not (item.evidence_type == "memory" and item.metadata.get("ephemeral"))
    ]

    for item in combined:
        item.content = compress_evidence_content(item.content)

    selected, budget_meta = apply_context_budget(combined, max_context_tokens=max_context_tokens)
    summary = {
        "total_evidence": len(combined),
        "selected_evidence": len(selected),
        **budget_meta,
    }
    return selected, summary
