"""RAG API schemas."""

from uuid import UUID

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    doc_type: str | None = None
    supplier_id: UUID | None = None
    chunk_size: int = Field(default=512)


class CitationItem(BaseModel):
    document_id: UUID
    chunk_id: UUID | None = None
    chunk_index: int
    title: str
    score: float
    snippet: str


class RAGRetrievalMeta(BaseModel):
    top_k: int
    result_count: int
    filter_applied: dict
    latency_ms: int | None = None


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    citations: list[CitationItem]
    trace_id: str
    status: str
    retrieval: RAGRetrievalMeta
