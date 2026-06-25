"""Memory type constants and dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class MemoryScope(StrEnum):
    USER = "user"
    BUSINESS = "business"
    SESSION = "session"


class UserMemoryType(StrEnum):
    PREFERENCE = "preference"
    FOCUS_SUPPLIER = "focus_supplier"
    REPORT_STYLE = "report_style"
    FEEDBACK = "feedback"


class BusinessMemoryType(StrEnum):
    BUSINESS_DECISION = "business_decision"
    SUPPLIER_RISK_HISTORY = "supplier_risk_history"
    RECOMMENDATION_FEEDBACK = "recommendation_feedback"


USER_MEMORY_TYPES = frozenset(item.value for item in UserMemoryType)
BUSINESS_MEMORY_TYPES = frozenset(item.value for item in BusinessMemoryType)


@dataclass
class SessionMessage:
    role: str
    content: str
    timestamp: str
    entities: dict[str, str] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "entities": self.entities,
            "evidence_refs": self.evidence_refs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMessage:
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", ""),
            entities=data.get("entities") or {},
            evidence_refs=data.get("evidence_refs") or [],
        )


@dataclass
class MemoryRecord:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    memory_type: str
    content: str
    summary: str | None
    supplier_id: UUID | None
    source_agent_run_id: UUID | None
    confidence: float
    importance: float
    expires_at: datetime | None
    metadata_: dict[str, Any]
    scope: str = MemoryScope.USER

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "user_id": str(self.user_id),
            "memory_type": self.memory_type,
            "content": self.content,
            "summary": self.summary,
            "supplier_id": str(self.supplier_id) if self.supplier_id else None,
            "source_agent_run_id": str(self.source_agent_run_id) if self.source_agent_run_id else None,
            "confidence": self.confidence,
            "importance": self.importance,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "metadata": self.metadata_,
            "scope": self.scope,
        }


@dataclass
class MemoryWriteEvent:
    content: str
    memory_type: str | None = None
    scope: str = MemoryScope.USER
    supplier_id: UUID | None = None
    source_agent_run_id: UUID | None = None
    confidence: float = 0.8
    importance: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    is_user_explicit: bool = False
    is_analysis_conclusion: bool = False
