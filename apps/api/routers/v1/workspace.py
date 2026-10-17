"""Enterprise API: durable commands, typed error codes and local subscriptions."""

import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import UUID
from fastapi import Request, APIRouter, Depends, File, Form, Header, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select, func
from sqlalchemy.orm import defer
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict
from apps.api.deps import get_user_context
from packages.authz.rbac import UserContext
from packages.common.db.session import get_db_session
from packages.common.db.models.workspace import (
    WorkspaceRecord,
    ImportBatch,
    ActionTask,
    WorkspaceActivity,
    WorkspaceReport,
    LocalSubscription,
    LocalEvent,
)
from packages.operations import service as ops
from packages.operations.files import read_table, template, MAX_BYTES
from packages.operations.schemas import (
    ImportKind,
    Kind,
    Source,
    TaskCreate,
    TaskChange,
    Capture,
    ReportRequest,
    SubscriptionCreate,
    ROWS,
)
from packages.operations.reports import create_report

router = APIRouter(prefix="/workspace", tags=["enterprise-workspace"])


async def member(user: UserContext = Depends(get_user_context)):
    if not user.is_member:
        raise ops.BusinessError(
            "membership_required", "Enterprise membership required", 403
        )
    return user


async def commit_command(session, user, operation, key, body, command):
    try:
        result = await ops.idempotent(session, user, operation, key, body, command)
        await session.commit()
        return result
    except Exception:
        await session.rollback()
        raise


@router.get("/openapi")
async def enterprise_openapi(request: Request, user=Depends(member)):
    spec = request.app.openapi()
    return {
        **spec,
        "info": {**spec["info"], "title": "SupplyGuard Enterprise Workspace API"},
        "paths": {
            path: value
            for path, value in spec["paths"].items()
            if path.startswith("/api/v1/workspace")
            or path in {"/api/v1/auth/login", "/api/v1/auth/me"}
        },
        "servers": [{"url": "/"}],
    }


@router.get("/schema")
def schemas(user=Depends(member)):
    return {
        "version": "workspace-v1",
        "tenant_id": str(user.tenant_id),
        "fields": {k: list(v.model_fields) for k, v in ROWS.items()},
        "import_order": ["site", "order", "shipment", "event"],
        "source_types": ["synthetic", "enterprise_uploaded"],
        "limits": {
            "file_mib": 2,
            "rows": 1000,
            "columns": 40,
            "preview_expiry_hours": 24,
            "report_expiry_hours": 24,
        },
        "events_delivery": "local_polling_only; no external delivery",
    }


@router.get("/templates/{kind}")
def download_template(
    kind: ImportKind, format: Literal["csv", "xlsx"] = "csv", user=Depends(member)
):
    content = template(kind, format)
    return Response(
        content,
        media_type=(
            "text/csv; charset=utf-8"
            if format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{kind}-template.{format}"'
        },
    )


@router.post("/imports/inspect")
async def inspect_file(file: UploadFile = File(...), user=Depends(member)):
    content = await file.read(MAX_BYTES + 1)
    try:
        headers, rows = read_table(content, file.filename or "")
    except Exception as exc:
        raise ops.BusinessError(
            "invalid_file", "Invalid CSV/XLSX: " + str(exc)[:200]
        ) from exc
    return {
        "headers": headers,
        "row_count": len(rows),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


@router.post("/imports/preview")
async def preview(
    kind: ImportKind = Form(...),
    source_type: Source = Form(...),
    mapping: str = Form(...),
    file: UploadFile = File(...),
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    content = await file.read(MAX_BYTES + 1)
    try:
        headers, raw = read_table(content, file.filename or "")
        mapped = json.loads(mapping)
        filename = Path((file.filename or "upload").replace("\\", "/")).name
        sha = hashlib.sha256(content).hexdigest()

        async def command():
            try:
                return await ops.stage(
                    session,
                    user,
                    kind,
                    filename,
                    source_type,
                    sha,
                    headers,
                    raw,
                    mapped,
                )
            except ValueError as exc:
                raise ops.BusinessError("invalid_mapping", str(exc)) from exc

        return await commit_command(
            session,
            user,
            "import.preview",
            key,
            [kind, source_type, sha, mapped],
            command,
        )
    except (ValueError, UnicodeError) as exc:
        raise ops.BusinessError("invalid_file", str(exc)[:200]) from exc


@router.post("/imports/{batch_id}/confirm")
async def confirm_import(
    batch_id: UUID,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await commit_command(
        session,
        user,
        "import.confirm",
        key,
        {"batch_id": str(batch_id)},
        lambda: ops.confirm(session, user, batch_id),
    )


async def page(session, model, user, limit, offset, filters=()):
    where = [model.tenant_id == user.tenant_id, *filters]
    count = (
        await session.execute(select(func.count()).select_from(model).where(*where))
    ).scalar_one()
    statement = select(model)
    if model is WorkspaceReport:
        statement = statement.options(defer(WorkspaceReport.content))
    elif model is ImportBatch:
        statement = statement.options(defer(ImportBatch.rows))
    rows = (
        (
            await session.execute(
                statement.where(*where)
                .order_by(model.created_at.desc(), model.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return {
        "tenant_id": str(user.tenant_id),
        "items": [ops.view(x) for x in rows],
        "total": count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/records")
async def records(
    kind: Kind | None = None,
    q: str = Query(default="", max_length=100),
    source_type: (
        Literal["synthetic", "enterprise_uploaded", "public_historical"] | None
    ) = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    filters = []
    if kind:
        filters.append(WorkspaceRecord.kind == kind)
    if source_type:
        filters.append(WorkspaceRecord.source_type == source_type)
    if q:
        filters.append(
            WorkspaceRecord.code.contains(q, autoescape=True)
            | WorkspaceRecord.name.contains(q, autoescape=True)
        )
    return await page(session, WorkspaceRecord, user, limit, offset, filters)


@router.get("/records/{record_id}")
async def record(
    record_id: UUID,
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return ops.view(await ops.owned(session, WorkspaceRecord, user, record_id))


@router.get("/imports")
async def imports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await page(session, ImportBatch, user, limit, offset)


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: Literal["port-congestion", "tier2-shutdown", "regional-flood"]


@router.post("/demo-scenario")
async def demo(
    payload: DemoRequest,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await commit_command(
        session,
        user,
        "demo.archive",
        key,
        payload.model_dump(),
        lambda: ops.demo_scenario(session, user, payload.scenario_id),
    )


@router.post("/captures")
async def capture(
    payload: Capture,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await commit_command(
        session,
        user,
        "capture",
        key,
        payload.model_dump(mode="json"),
        lambda: ops.capture(session, user, payload),
    )


@router.get("/members")
async def members(
    user=Depends(member), session: AsyncSession = Depends(get_db_session)
):
    return {"items": await ops.members(session, user)}


@router.get("/tasks")
async def tasks(
    state: (
        Literal["open", "in_progress", "pending_verification", "completed", "cancelled"]
        | None
    ) = None,
    limit: int = Query(30, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await page(
        session,
        ActionTask,
        user,
        limit,
        offset,
        [ActionTask.state == state] if state else [],
    )


@router.post("/tasks")
async def create_task(
    payload: TaskCreate,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await commit_command(
        session,
        user,
        "task.create",
        key,
        payload.model_dump(mode="json"),
        lambda: ops.create_task(session, user, payload),
    )


@router.get("/tasks/{task_id}")
async def task(
    task_id: UUID, user=Depends(member), session: AsyncSession = Depends(get_db_session)
):
    return ops.view(await ops.owned(session, ActionTask, user, task_id))


@router.patch("/tasks/{task_id}")
async def change_task(
    task_id: UUID,
    payload: TaskChange,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await commit_command(
        session,
        user,
        "task.change:" + str(task_id),
        key,
        payload.model_dump(mode="json"),
        lambda: ops.change_task(session, user, task_id, payload),
    )


@router.get("/tasks/{task_id}/history")
async def history(
    task_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    await ops.owned(session, ActionTask, user, task_id)
    return await page(
        session,
        WorkspaceActivity,
        user,
        limit,
        offset,
        [WorkspaceActivity.resource_id == str(task_id)],
    )


@router.get("/reports")
async def reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await page(session, WorkspaceReport, user, limit, offset)


@router.post("/reports")
async def report(
    payload: ReportRequest,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    return await commit_command(
        session,
        user,
        "report.create",
        key,
        payload.model_dump(mode="json"),
        lambda: create_report(session, user, payload),
    )


@router.get("/reports/{report_id}/download")
async def download(
    report_id: UUID,
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    r = await ops.owned(session, WorkspaceReport, user, report_id)
    if r.expires_at <= ops.now():
        raise ops.BusinessError(
            "report_expired", "Download expired; generate a fresh report", 410
        )
    if hashlib.sha256(r.content).hexdigest() != r.sha256:
        raise ops.BusinessError(
            "artifact_corrupt", "Report integrity check failed", 500
        )
    await ops.activity(session, user, r.id, "report.downloaded", {"sha256": r.sha256})
    await session.commit()
    return Response(
        r.content,
        media_type=(
            "text/csv; charset=utf-8"
            if r.format == "csv"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{r.filename}"',
            "Cache-Control": "no-store",
            "X-Content-SHA256": r.sha256,
        },
    )


@router.post("/subscriptions")
async def subscribe(
    payload: SubscriptionCreate,
    key: str = Header(..., alias="Idempotency-Key", min_length=1, max_length=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    async def command():
        r = LocalSubscription(
            tenant_id=user.tenant_id, created_by=user.user_id, **payload.model_dump()
        )
        session.add(r)
        await session.flush()
        await ops.activity(
            session,
            user,
            r.id,
            "subscription.created",
            {"topics": r.topics, "delivery": "local_polling_only"},
        )
        return ops.view(r)

    return await commit_command(
        session, user, "subscription.create", key, payload.model_dump(), command
    )


@router.get("/subscriptions")
async def subscriptions(
    user=Depends(member), session: AsyncSession = Depends(get_db_session)
):
    return await page(session, LocalSubscription, user, 100, 0)


@router.get("/subscriptions/{subscription_id}/events")
async def events(
    subscription_id: UUID,
    after: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    user=Depends(member),
    session: AsyncSession = Depends(get_db_session),
):
    r = await ops.owned(session, LocalSubscription, user, subscription_id)
    rows = (
        (
            await session.execute(
                select(LocalEvent)
                .where(
                    LocalEvent.tenant_id == user.tenant_id,
                    LocalEvent.id > after,
                    LocalEvent.topic.in_(r.topics),
                )
                .order_by(LocalEvent.id)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return {
        "items": [
            {
                "id": e.id,
                "topic": e.topic,
                "resource_id": e.resource_id,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in rows
        ],
        "next_cursor": rows[-1].id if rows else after,
        "delivery": "local_only",
        "external_sent": False,
    }
