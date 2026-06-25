"""Merge Secure RAG, GraphRAG, and Memory evidence."""

from __future__ import annotations

from packages.agents.evidence_aggregator import aggregate_evidence
from packages.agents.evidence_types import EvidenceItem
from packages.agents.state import AgentState
from packages.common.config import get_settings


async def evidence_aggregator_node(state: AgentState) -> AgentState:
    settings = get_settings()
    max_tokens = getattr(settings, "MAX_CONTEXT_TOKENS", 8000)

    selected, summary = aggregate_evidence(
        rag_chunks=state.get("retrieved_chunks") or [],
        graph_paths=state.get("graph_paths") or [],
        memory_evidence=state.get("memory_evidence") or [],
        tool_evidence=state.get("tool_evidence") or [],
        max_context_tokens=max_tokens,
    )

    return {
        "unified_evidence": selected,
        "aggregated_evidence": [item.to_dict() for item in selected],
        "evidence_summary": summary,
        "context_budget": {
            "max_tokens": summary.get("max_tokens", max_tokens),
            "used_tokens": summary.get("used_tokens", 0),
        },
        "nodes_executed": ["evidence_aggregator"],
    }
