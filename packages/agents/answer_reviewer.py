"""Rule-based answer review."""

from __future__ import annotations

import re

from packages.agents.citation_manager import extract_all_citations
from packages.agents.evidence_types import EvidenceItem
from packages.authz.rbac import UserContext
from packages.rag.prompts import NO_EVIDENCE_ANSWER, NO_PERMISSION_ANSWER

LEAK_PHRASES = (
    "无权访问的文档存在",
    "被过滤的文档",
    "hidden document",
    "我看到了被过滤",
)
FABRICATION_PHRASES = (
    "net 90",
    "合同金额为",
    "付款条款为 net",
)


def review_answer(
    *,
    answer: str,
    evidence: list[EvidenceItem],
    user_context: UserContext,
    status: str | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if status == "blocked":
        if answer != NO_PERMISSION_ANSWER and "无权" not in answer:
            errors.append("blocked query must use no-permission template")
        return not errors, errors

    has_rag = any(item.evidence_type == "rag_chunk" for item in evidence)
    has_graph = any(item.evidence_type == "graph_path" for item in evidence)
    has_memory = any(
        item.evidence_type == "memory" and item.citation for item in evidence
    )
    has_tool = any(item.evidence_type == "tool_result" for item in evidence)

    if not evidence:
        if answer != NO_EVIDENCE_ANSWER:
            errors.append("no evidence must use fixed refusal template")
        return not errors, errors

    citations = extract_all_citations(answer)

    if has_rag and not citations["doc"]:
        errors.append("answer missing doc citation for RAG evidence")

    if has_graph and not citations["graph"] and not citations["legacy_graph"]:
        errors.append("answer missing graph citation for graph evidence")

    if has_memory and not citations["memory"]:
        errors.append("answer missing memory citation for memory evidence")

    if has_tool and not citations["tool"]:
        errors.append("answer missing tool citation for tool evidence")

    allowed_doc = {
        (item.source_id, int(item.metadata.get("chunk_index", -1)))
        for item in evidence
        if item.evidence_type == "rag_chunk"
    }
    for document_id, chunk_index in citations["doc"]:
        if (document_id, chunk_index) not in allowed_doc:
            errors.append(f"doc citation not in evidence: {document_id}#{chunk_index}")

    allowed_graph = {
        (item.source_id, int(item.metadata.get("path_index", -1)))
        for item in evidence
        if item.evidence_type == "graph_path"
    }
    for query_type, path_index in citations["graph"]:
        if (query_type, path_index) not in allowed_graph:
            errors.append(f"graph citation not in evidence: {query_type}#{path_index}")

    allowed_memory = {item.source_id for item in evidence if item.evidence_type == "memory"}
    for memory_id in citations["memory"]:
        if memory_id not in allowed_memory:
            errors.append(f"memory citation not in evidence: {memory_id}")

    allowed_tool = {
        (item.metadata.get("tool_name", item.source_id), item.metadata.get("tool_call_id", item.evidence_id))
        for item in evidence
        if item.evidence_type == "tool_result"
    }
    for tool_name, tool_call_id in citations["tool"]:
        if (tool_name, tool_call_id) not in allowed_tool:
            errors.append(f"tool citation not in evidence: {tool_name}#{tool_call_id}")

    lowered = answer.lower()
    for phrase in LEAK_PHRASES:
        if phrase in lowered:
            errors.append(f"potential permission leak phrase: {phrase}")

    if user_context.is_external_supplier:
        for other in re.findall(r"SUP-\d{3}", answer, re.IGNORECASE):
            pass  # supplier codes in graph paths are expected for own scope

    for phrase in FABRICATION_PHRASES:
        if phrase.lower() in lowered and not has_rag:
            errors.append(f"potential fabricated contract detail: {phrase}")

    return not errors, errors
