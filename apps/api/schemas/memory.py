"""Memory API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SessionMemoryResponse(BaseModel):
    session_id: str
    messages: list[dict]


class LongTermMemoryItem(BaseModel):
    id: str
    memory_type: str
    content: str
    summary: str | None = None
    supplier_id: str | None = None
    confidence: float
    importance: float
    metadata: dict = Field(default_factory=dict)


class LongTermMemoryListResponse(BaseModel):
    items: list[LongTermMemoryItem]


class LongTermMemoryCreateRequest(BaseModel):
    content: str = Field(min_length=8)
    memory_type: str | None = None
    supplier_id: str | None = None
    importance: float = Field(default=0.5, ge=0, le=1)


class LongTermMemoryCreateResponse(BaseModel):
    id: str
    memory_type: str
    content: str
