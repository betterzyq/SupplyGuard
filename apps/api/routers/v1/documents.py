"""Document upload and management routes."""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.deps import get_current_user, get_user_context
from apps.api.schemas.document import DocumentUploadResponse
from packages.authz.constants import security_level_to_rank
from packages.authz.rbac import UserContext, can_upload_document
from packages.common.db.models.document import Document
from packages.common.db.models.user import User
from packages.common.db.session import get_db_session
from packages.rag.chunking import ALLOWED_CHUNK_SIZES
from packages.rag.ingest import ingest_uploaded_file, save_raw_file

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    doc_type: str = Form(...),
    department: str = Form(...),
    security_level: str = Form(...),
    access_scope: str = Form(...),
    allowed_roles: str = Form(default="[]"),
    allowed_users: str = Form(default="[]"),
    supplier_id: uuid.UUID | None = Form(default=None),
    chunk_size: int = Form(default=512),
    user: User = Depends(get_current_user),
    user_context: UserContext = Depends(get_user_context),
    session: AsyncSession = Depends(get_db_session),
) -> DocumentUploadResponse:
    if not can_upload_document(user_context):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="upload not permitted")

    if chunk_size not in ALLOWED_CHUNK_SIZES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"chunk_size must be one of {sorted(ALLOWED_CHUNK_SIZES)}",
        )

    filename = file.filename or "upload.txt"
    suffix = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported file type; allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    try:
        roles = json.loads(allowed_roles) if allowed_roles else []
        users = json.loads(allowed_users) if allowed_users else []
        if not isinstance(roles, list) or not isinstance(users, list):
            raise ValueError("allowed_roles and allowed_users must be JSON arrays")
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="empty file")

    mime_type = file.content_type or "text/plain"
    document = Document(
        tenant_id=user.tenant_id,
        title=title,
        doc_type=doc_type,
        source_uri="",
        file_name=filename,
        mime_type=mime_type,
        security_level=security_level,
        security_level_rank=security_level_to_rank(security_level),
        access_scope=access_scope,
        department=department,
        allowed_roles=roles,
        allowed_users=users,
        supplier_id=supplier_id,
        status="processing",
        metadata_={},
        uploaded_by=user.id,
    )
    session.add(document)
    await session.flush()

    raw_path = await save_raw_file(user.tenant_id, document.id, filename, content)
    document.source_uri = str(raw_path)
    await session.flush()

    try:
        chunk_count = await ingest_uploaded_file(session, document, raw_path, chunk_size=chunk_size)
        await session.commit()
    except Exception as exc:
        await session.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return DocumentUploadResponse(
        document_id=document.id,
        title=document.title,
        status=document.status,
        chunk_count=chunk_count,
        source_uri=document.source_uri,
    )
