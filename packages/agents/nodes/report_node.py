"""Report generation node."""

from __future__ import annotations

from packages.agents.citation_manager import build_citation_footer
from packages.agents.evidence_types import EvidenceItem
from packages.agents.state import AgentState
from packages.common.llm.factory import get_llm_client
from packages.graphrag.answer_format import build_graph_answer
from packages.rag.citations import Citation
from packages.rag.prompts import (
    NO_EVIDENCE_ANSWER,
    NO_PERMISSION_ANSWER,
    RAG_SYSTEM_PROMPT,
    build_rag_user_prompt,
)


def _evidence_block(items: list[EvidenceItem]) -> str:
    parts: list[str] = []
    for item in items:
        label = item.evidence_type.upper()
        cite = item.citation or ""
        parts.append(f"### {label} {cite}\n{item.content}")
    return "\n\n".join(parts)


def _memory_primary_answer(query: str, items: list[EvidenceItem]) -> str:
    memory_items = [item for item in items if item.evidence_type == "memory"]
    if not memory_items:
        return NO_EVIDENCE_ANSWER
    lines = ["根据历史记忆与上一轮分析：", ""]
    for index, item in enumerate(memory_items[:5], start=1):
        lines.append(f"{index}. {item.content}")
    lines.append("")
    lines.append("记忆证据来源：")
    for item in memory_items[:5]:
        if item.citation:
            lines.append(f"* {item.citation}")
    return "\n".join(lines)


def _tool_primary_answer(query: str, items: list[EvidenceItem]) -> str:
    tool_items = [item for item in items if item.evidence_type == "tool_result"]
    if not tool_items:
        return NO_EVIDENCE_ANSWER
    lines = ["根据工具查询结果：", ""]
    for item in tool_items:
        status = item.metadata.get("status", "success")
        if status == "approval_required":
            lines.append(f"- {item.source_title}: 需要审批后才能执行。")
        elif status == "denied":
            lines.append(f"- {item.source_title}: 权限不足，无法调用。")
        else:
            lines.append(f"- {item.source_title}: {item.content[:500]}")
    lines.append("")
    footer = build_citation_footer(tool_items)
    if footer:
        lines.append(footer)
    return "\n".join(lines)


async def report_node(state: AgentState) -> AgentState:
    if state.get("status") == "blocked":
        return {
            "draft_answer": state.get("draft_answer") or NO_PERMISSION_ANSWER,
            "citations": [],
            "token_usage": {},
            "status": "blocked",
            "nodes_executed": ["report"],
        }

    query = state["query"]
    route_mode = state.get("route_mode") or "rag"
    unified: list[EvidenceItem] = state.get("unified_evidence") or []
    chunks = state.get("retrieved_chunks") or []
    graph_result = state.get("graph_result")

    if route_mode == "tool" and unified:
        answer = _tool_primary_answer(query, unified)
        return {
            "draft_answer": answer,
            "citations": [],
            "token_usage": {},
            "status": "answered",
            "nodes_executed": ["report"],
        }

    if not unified:
        if graph_result and graph_result.graph_paths and route_mode == "graphrag":
            answer = build_graph_answer(graph_result)
            return {
                "draft_answer": answer,
                "citations": [],
                "token_usage": {},
                "status": "answered",
                "nodes_executed": ["report"],
            }
        return {
            "draft_answer": NO_EVIDENCE_ANSWER,
            "citations": [],
            "token_usage": {},
            "status": "no_evidence",
            "nodes_executed": ["report"],
        }

    memory_only = (
        route_mode in {"memory", "memory_rag"}
        and not any(item.evidence_type == "rag_chunk" for item in unified)
        and not any(item.evidence_type == "graph_path" for item in unified)
        and any(item.evidence_type == "memory" for item in unified)
    )

    if memory_only:
        answer = _memory_primary_answer(query, unified)
        return {
            "draft_answer": answer,
            "citations": [],
            "token_usage": {},
            "status": "answered",
            "nodes_executed": ["report"],
        }

    if route_mode == "graphrag" and graph_result and not any(
        item.evidence_type == "rag_chunk" for item in unified
    ):
        answer = build_graph_answer(graph_result)
        footer = build_citation_footer([item for item in unified if item.evidence_type == "graph_path"])
        if footer:
            answer = f"{answer}\n\n{footer}"
        return {
            "draft_answer": answer,
            "citations": [],
            "token_usage": {},
            "status": "answered",
            "nodes_executed": ["report"],
        }

    llm = get_llm_client()
    evidence_block = _evidence_block(unified)
    chat_result = await llm.chat(
        [
            {"role": "system", "content": RAG_SYSTEM_PROMPT},
            {"role": "user", "content": build_rag_user_prompt(query, evidence_block)},
        ]
    )
    answer = (chat_result.content or "").strip() or NO_EVIDENCE_ANSWER
    footer = build_citation_footer(unified)
    if footer and "证据来源" not in answer:
        answer = f"{answer}\n\n{footer}"

    citations = [
        Citation(
            document_id=item.source_id,
            chunk_id=item.evidence_id,
            chunk_index=int(item.metadata.get("chunk_index", 0)),
            title=item.source_title,
            score=item.score,
            snippet=item.content[:280],
        )
        for item in unified
        if item.evidence_type == "rag_chunk"
    ]

    return {
        "draft_answer": answer,
        "citations": citations,
        "token_usage": chat_result.token_usage,
        "status": "answered",
        "nodes_executed": ["report"],
    }
