"""GraphRAG API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GraphRAGQueryRequest(BaseModel):
    query: str
    query_type: str
    entity_code: str | None = None
    top_k: int = Field(default=20, ge=1, le=100)


class GraphPathItem(BaseModel):
    path_index: int
    path_text: str
    nodes: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    template_id: str
    graph_path_ref: str | None = None


class GraphRAGQueryResponse(BaseModel):
    query: str
    query_type: str
    matched_entities: list[dict[str, Any]]
    graph_paths: list[GraphPathItem]
    affected_suppliers: list[str]
    affected_materials: list[str]
    affected_products: list[str]
    affected_orders: list[str]
    affected_customers: list[str]
    cypher_template: str
    trace_id: str
    latency_ms: int
    result_count: int = 0
    permission_decision: str = "allowed"
    error_message: str | None = None
