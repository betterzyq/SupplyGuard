"""Context token budget control."""

from __future__ import annotations

from packages.agents.evidence_types import EvidenceItem


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def apply_context_budget(
    evidence: list[EvidenceItem],
    *,
    max_context_tokens: int = 8000,
) -> tuple[list[EvidenceItem], dict]:
    if not evidence:
        return [], {"max_tokens": max_context_tokens, "used_tokens": 0}

    rag_items = [item for item in evidence if item.evidence_type == "rag_chunk"]
    graph_items = [item for item in evidence if item.evidence_type == "graph_path"]
    memory_items = [item for item in evidence if item.evidence_type == "memory"]

    rag_items.sort(key=lambda item: item.score, reverse=True)
    graph_items.sort(key=lambda item: item.score, reverse=True)
    memory_items.sort(key=lambda item: item.score, reverse=True)

    memory_cap = int(max_context_tokens * 0.2)
    selected: list[EvidenceItem] = []
    used = 0

    def add_items(items: list[EvidenceItem], *, min_keep: int = 0, cap: int | None = None) -> None:
        nonlocal used
        kept = 0
        for item in items:
            tokens = estimate_tokens(item.content)
            if cap is not None and item.evidence_type == "memory":
                mem_used = sum(estimate_tokens(x.content) for x in selected if x.evidence_type == "memory")
                if mem_used + tokens > cap and kept >= min_keep:
                    continue
            if used + tokens > max_context_tokens and kept >= min_keep:
                continue
            selected.append(item)
            used += tokens
            kept += 1

    add_items(rag_items, min_keep=min(3, len(rag_items)))
    add_items(graph_items, min_keep=min(3, len(graph_items)))
    add_items(memory_items, min_keep=0, cap=memory_cap)

    return selected, {
        "max_tokens": max_context_tokens,
        "used_tokens": used,
        "rag_count": len([x for x in selected if x.evidence_type == "rag_chunk"]),
        "graph_count": len([x for x in selected if x.evidence_type == "graph_path"]),
        "memory_count": len([x for x in selected if x.evidence_type == "memory"]),
    }
