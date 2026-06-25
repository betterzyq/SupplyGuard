"""Document ingest pipeline."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.common.db.models.document import Document, DocumentChunk
from packages.common.embedding.openai_compatible import get_embedding_client
from packages.rag.chunking import chunk_text
from packages.rag.parsers.pdf_parser import parse_pdf
from packages.rag.parsers.text_parser import parse_text
from packages.rag.vector_store import delete_document_points, upsert_chunks

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"

MIME_BY_SUFFIX = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
}


def raw_dir(tenant_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    return DATA_DIR / "raw" / str(tenant_id) / str(document_id)


def processed_dir(tenant_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    return DATA_DIR / "processed" / str(tenant_id) / str(document_id)


def parse_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return parse_text(path, mime_type=MIME_BY_SUFFIX[suffix]).text
    if suffix == ".pdf":
        return parse_pdf(path).text
    raise ValueError(f"Unsupported file type: {suffix}")


async def save_raw_file(
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    filename: str,
    content: bytes,
) -> Path:
    target_dir = raw_dir(tenant_id, document_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(content)
    return target_path


async def save_processed_text(
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    text: str,
) -> Path:
    target_dir = processed_dir(tenant_id, document_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "content.txt"
    target_path.write_text(text, encoding="utf-8")
    return target_path


async def index_document_text(
    session: AsyncSession,
    document: Document,
    text: str,
    *,
    chunk_size: int = 512,
    reindex: bool = False,
) -> int:
    if reindex:
        await delete_document_points(document.id)
        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )
        await session.flush()

    document.status = "processing"
    metadata = dict(document.metadata_ or {})
    metadata.pop("error", None)
    document.metadata_ = metadata
    await session.flush()

    try:
        processed_path = await save_processed_text(document.tenant_id, document.id, text)
        document.source_uri = str(processed_path.relative_to(PROJECT_ROOT))
        chunks = chunk_text(text, chunk_size=chunk_size)
        if not chunks:
            raise ValueError("No chunks generated from document text")

        chunk_models: list[DocumentChunk] = []
        for piece in chunks:
            chunk = DocumentChunk(
                tenant_id=document.tenant_id,
                document_id=document.id,
                chunk_index=piece.chunk_index,
                content=piece.content,
                token_count=piece.token_count,
                security_level=document.security_level,
                security_level_rank=document.security_level_rank,
                access_scope=document.access_scope,
                department=document.department,
                allowed_roles=document.allowed_roles,
                allowed_users=document.allowed_users,
                supplier_id=document.supplier_id,
                metadata_={"chunk_size": chunk_size},
            )
            session.add(chunk)
            chunk_models.append(chunk)
        await session.flush()

        embedding_client = get_embedding_client()
        vectors = await embedding_client.embed_texts([item.content for item in chunk_models])
        for chunk_model, vector in zip(chunk_models, vectors, strict=True):
            chunk_model.embedding_id = str(chunk_model.id)

        await upsert_chunks(document, chunk_models, vectors)
        document.status = "indexed"
        document.metadata_ = {**metadata, "chunk_count": len(chunk_models), "chunk_size": chunk_size}
        await session.flush()
        return len(chunk_models)
    except Exception as exc:
        document.status = "failed"
        error_message = str(exc).strip() or f"{type(exc).__name__}"
        document.metadata_ = {**metadata, "error": error_message}
        await session.flush()
        raise RuntimeError(error_message) from exc


async def ingest_uploaded_file(
    session: AsyncSession,
    document: Document,
    file_path: Path,
    *,
    chunk_size: int = 512,
) -> int:
    text = parse_file(file_path)
    return await index_document_text(session, document, text, chunk_size=chunk_size, reindex=False)


async def reindex_existing_document(
    session: AsyncSession,
    document_id: uuid.UUID,
    *,
    text: str | None = None,
    source_path: Path | None = None,
    chunk_size: int = 512,
) -> int:
    document = (
        await session.execute(select(Document).where(Document.id == document_id))
    ).scalar_one()
    if text is None:
        if source_path is None:
            raise ValueError("text or source_path required")
        text = parse_file(source_path)
    return await index_document_text(
        session,
        document,
        text,
        chunk_size=chunk_size,
        reindex=True,
    )
