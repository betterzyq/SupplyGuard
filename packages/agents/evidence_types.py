"""Unified evidence item model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    evidence_id: str
    evidence_type: str  # rag_chunk | graph_path | memory
    source_id: str
    source_title: str
    content: str
    score: float = 0.0
    confidence: float = 0.0
    permission_scope: str = ""
    citation: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type,
            "source_id": self.source_id,
            "source_title": self.source_title,
            "content": self.content,
            "score": self.score,
            "confidence": self.confidence,
            "permission_scope": self.permission_scope,
            "citation": self.citation,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceItem:
        return cls(
            evidence_id=str(data.get("evidence_id", "")),
            evidence_type=str(data.get("evidence_type", "")),
            source_id=str(data.get("source_id", "")),
            source_title=str(data.get("source_title", "")),
            content=str(data.get("content", "")),
            score=float(data.get("score", 0)),
            confidence=float(data.get("confidence", 0)),
            permission_scope=str(data.get("permission_scope", "")),
            citation=data.get("citation"),
            metadata=data.get("metadata") or {},
        )
