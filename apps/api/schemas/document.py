"""Document API schemas."""

from uuid import UUID

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    title: str
    status: str
    chunk_count: int
    source_uri: str


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    doc_type: str
    status: str
    security_level: str
    access_scope: str
