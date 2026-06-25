"""Citation formatting and parsing."""

from __future__ import annotations

import re
from typing import Any

from packages.agents.evidence_types import EvidenceItem

DOC_CITATION = re.compile(r"\[doc:([0-9a-f\-]+)#chunk:(\d+)\]", re.IGNORECASE)
GRAPH_CITATION = re.compile(r"\[graph:([\w_]+)#path:(\d+)\]", re.IGNORECASE)
MEMORY_CITATION = re.compile(r"\[memory:([0-9a-f\-]+)\]", re.IGNORECASE)
TOOL_CITATION = re.compile(r"\[tool:([\w_]+)#([0-9a-f\-]+)\]", re.IGNORECASE)
LEGACY_GRAPH = re.compile(r"graph_path:\s*([\w#_\-]+)", re.IGNORECASE)


def format_doc_citation(document_id: str, chunk_index: int) -> str:
    return f"[doc:{document_id}#chunk:{chunk_index}]"


def format_graph_citation(query_type: str, path_index: int) -> str:
    return f"[graph:{query_type}#path:{path_index}]"


def format_memory_citation(memory_id: str) -> str:
    return f"[memory:{memory_id}]"


def format_tool_citation(tool_name: str, tool_call_id: str) -> str:
    return f"[tool:{tool_name}#{tool_call_id}]"


def build_citation_footer(evidence: list[EvidenceItem]) -> str:
    lines: list[str] = []
    for item in evidence:
        if item.citation:
            lines.append(f"* {item.citation}")
    if not lines:
        return ""
    return "证据来源：\n" + "\n".join(lines)


def extract_all_citations(answer: str) -> dict[str, list[tuple]]:
    return {
        "doc": DOC_CITATION.findall(answer),
        "graph": GRAPH_CITATION.findall(answer),
        "memory": MEMORY_CITATION.findall(answer),
        "tool": TOOL_CITATION.findall(answer),
        "legacy_graph": LEGACY_GRAPH.findall(answer),
    }


def allowed_citations_from_evidence(evidence: list[EvidenceItem]) -> dict[str, set]:
    allowed = {"doc": set(), "graph": set(), "memory": set(), "tool": set()}
    for item in evidence:
        if item.evidence_type == "rag_chunk" and item.citation:
            match = DOC_CITATION.search(item.citation)
            if match:
                allowed["doc"].add((match.group(1), int(match.group(2))))
        elif item.evidence_type == "graph_path" and item.citation:
            match = GRAPH_CITATION.search(item.citation)
            if match:
                allowed["graph"].add((match.group(1), int(match.group(2))))
        elif item.evidence_type == "memory" and item.citation:
            match = MEMORY_CITATION.search(item.citation)
            if match:
                allowed["memory"].add(match.group(1))
        elif item.evidence_type == "tool_result" and item.citation:
            match = TOOL_CITATION.search(item.citation)
            if match:
                allowed["tool"].add((match.group(1), match.group(2)))
    return allowed
