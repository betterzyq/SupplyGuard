"""Document and document chunk models."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.common.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Document(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "documents"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    security_level: Mapped[str] = mapped_column(String(32), nullable=False)
    security_level_rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    access_scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_roles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    allowed_users: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="indexed", nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_doc_index"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    security_level: Mapped[str] = mapped_column(String(32), nullable=False)
    security_level_rank: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    access_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    department: Mapped[str] = mapped_column(String(64), nullable=False)
    allowed_roles: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    allowed_users: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    document: Mapped["Document"] = relationship(back_populates="chunks")
