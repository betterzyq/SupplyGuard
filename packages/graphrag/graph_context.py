"""Graph path and retrieval result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    label: str
    code: str
    name: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "code": self.code,
            "name": self.name,
            "properties": self.properties,
        }


@dataclass
class GraphRelationship:
    type: str
    start_code: str
    end_code: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "start_code": self.start_code,
            "end_code": self.end_code,
            "properties": self.properties,
        }


@dataclass
class GraphPath:
    path_index: int
    path_text: str
    nodes: list[GraphNode]
    relationships: list[GraphRelationship]
    template_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_index": self.path_index,
            "path_text": self.path_text,
            "nodes": [node.to_dict() for node in self.nodes],
            "relationships": [rel.to_dict() for rel in self.relationships],
            "template_id": self.template_id,
            "graph_path_ref": f"{self.template_id}#path_{self.path_index}",
        }


@dataclass
class GraphRetrievalResult:
    query: str
    query_type: str
    matched_entities: list[dict[str, Any]]
    graph_paths: list[GraphPath]
    affected_suppliers: list[str]
    affected_materials: list[str]
    affected_products: list[str]
    affected_orders: list[str]
    affected_customers: list[str]
    cypher_template: str
    cypher_query: str
    parameters: dict[str, Any]
    trace_id: str
    latency_ms: int
    result_count: int
    permission_decision: str = "allowed"
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_type": self.query_type,
            "matched_entities": self.matched_entities,
            "graph_paths": [path.to_dict() for path in self.graph_paths],
            "affected_suppliers": self.affected_suppliers,
            "affected_materials": self.affected_materials,
            "affected_products": self.affected_products,
            "affected_orders": self.affected_orders,
            "affected_customers": self.affected_customers,
            "cypher_template": self.cypher_template,
            "trace_id": self.trace_id,
            "latency_ms": self.latency_ms,
            "result_count": self.result_count,
            "permission_decision": self.permission_decision,
            "error_message": self.error_message,
        }
