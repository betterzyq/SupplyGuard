"""Agent workflow state."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from packages.agents.evidence_types import EvidenceItem
from packages.authz.rbac import PermissionDecision, UserContext
from packages.graphrag.graph_context import GraphPath, GraphRetrievalResult
from packages.rag.citations import Citation
from packages.rag.retriever import RetrievedChunk


class AgentState(TypedDict, total=False):
    query: str
    user_context: UserContext
    trace_id: str
    session_id: str
    agent_run_id: str
    top_k: int
    chunk_size_config: int
    doc_type: str | None
    supplier_id: str | None
    ip_address: str | None
    use_memory: bool
    db_session: Any
    permission_decision: PermissionDecision
    route_mode: str
    tool_name: str | None
    tool_input: dict[str, Any]
    tool_evidence: list[dict[str, Any]]
    graph_query_type: str
    graph_entity_code: str | None
    graph_result: GraphRetrievalResult
    graph_paths: list[GraphPath]
    graph_evidence: list[dict[str, Any]]
    memory_evidence: list[dict[str, Any]]
    recent_entities: dict[str, str]
    unified_evidence: list[EvidenceItem]
    aggregated_evidence: list[dict[str, Any]]
    evidence_summary: dict[str, Any]
    context_budget: dict[str, Any]
    memory_used: list[dict[str, Any]]
    memory_written: list[dict[str, Any]]
    retrieved_chunks: list[RetrievedChunk]
    evidence: list[dict[str, Any]]
    draft_answer: str
    final_answer: str
    citations: list[Citation]
    token_usage: dict[str, Any]
    latency_ms: int
    errors: Annotated[list[str], operator.add]
    nodes_executed: Annotated[list[str], operator.add]
    review_passed: bool
    status: str
