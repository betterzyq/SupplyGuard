"""Atomic tenant-scoped commands. Commit belongs to HTTP/tool caller."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from sqlalchemy import select, func, text
from packages.authz.rbac import UserContext
from packages.authz.audit import write_audit_log
from packages.common.db.models.user import User
from packages.common.db.models.role import Role, UserRole
from packages.common.db.models.workspace import (
    ImportBatch,
    WorkspaceRecord,
    RecordLink,
    ActionTask,
    WorkspaceActivity,
    IdempotencyRecord,
    LocalEvent,
    LocalSubscription,
    WorkspaceReport,
)
from .schemas import ROWS, references
from .files import normalize


class BusinessError(Exception):
    def __init__(self, code, message, status=422):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def now():
    return datetime.now(timezone.utc)


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()


def view(row):
    if isinstance(row, WorkspaceRecord):
        keys = [
            "id",
            "kind",
            "code",
            "name",
            "source_type",
            "source_ref",
            "import_batch_id",
            "payload",
            "created_at",
        ]
    elif isinstance(row, ActionTask):
        keys = [
            "id",
            "record_id",
            "title",
            "state",
            "version",
            "assignee_id",
            "due_at",
            "measures",
            "actual_cost_cny",
            "result",
            "created_by",
            "created_at",
            "updated_at",
        ]
    elif isinstance(row, ImportBatch):
        keys = [
            "id",
            "kind",
            "filename",
            "source_type",
            "source_sha256",
            "fingerprint",
            "mapping",
            "state",
            "expires_at",
            "confirmed_at",
            "created_at",
            "errors",
        ]
    elif isinstance(row, WorkspaceReport):
        keys = [
            "id",
            "kind",
            "format",
            "filename",
            "sha256",
            "summary",
            "created_at",
            "expires_at",
        ]
    elif isinstance(row, LocalSubscription):
        keys = ["id", "name", "topics", "created_at"]
    else:
        keys = ["id", "resource_id", "action", "actor_id", "detail", "created_at"]
    value = {k: getattr(row, k) for k in keys}
    return json.loads(json.dumps(value, default=str))


async def lock(session, user):
    if not user.is_member:
        raise BusinessError(
            "membership_required", "Enterprise membership required", 403
        )
    await session.execute(text("SELECT set_config('lock_timeout','3000ms',true)"))
    key = int.from_bytes(
        hashlib.sha256(("sg5:" + str(user.tenant_id)).encode()).digest()[:8],
        "big",
        signed=True,
    )
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})


async def owned(session, model, user, identifier, for_update=False):
    stmt = select(model).where(
        model.tenant_id == user.tenant_id, model.id == identifier
    )
    if for_update:
        stmt = stmt.with_for_update()
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise BusinessError("not_found", "Resource not found in this enterprise", 404)
    return row


async def record_by_code(session, user, kind, code):
    return (
        await session.execute(
            select(WorkspaceRecord).where(
                WorkspaceRecord.tenant_id == user.tenant_id,
                WorkspaceRecord.kind == kind,
                WorkspaceRecord.code == code,
            )
        )
    ).scalar_one_or_none()


async def activity(session, user, resource_id, action, detail):
    session.add(
        WorkspaceActivity(
            tenant_id=user.tenant_id,
            resource_id=str(resource_id),
            action=action,
            actor_id=user.user_id,
            detail=detail,
        )
    )
    await write_audit_log(
        session,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
        action=action,
        resource_type="enterprise_workspace",
        resource_id=str(resource_id),
        permission_decision="allowed",
        reason="enterprise-v2 tenant business operation",
        metadata=detail,
    )


async def emit(session, user, topic, identifier, payload):
    session.add(
        LocalEvent(
            tenant_id=user.tenant_id,
            topic=topic,
            resource_id=str(identifier),
            payload=payload,
        )
    )


async def idempotent(session, user, operation, key, body, command):
    if not key or len(key) > 100 or any(not (c.isalnum() or c in "-_.:") for c in key):
        raise BusinessError(
            "invalid_idempotency_key",
            "Idempotency-Key is required (1..100 letters/digits/-_.:)",
        )
    await lock(session, user)
    old = (
        await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.tenant_id == user.tenant_id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key == key,
            )
        )
    ).scalar_one_or_none()
    fingerprint = digest(body)
    if old:
        if old.request_sha256 != fingerprint:
            raise BusinessError(
                "idempotency_conflict", "Key was already used with different input", 409
            )
        return old.response
    result = await command()
    session.add(
        IdempotencyRecord(
            tenant_id=user.tenant_id,
            operation=operation,
            key=key,
            request_sha256=fingerprint,
            response=result,
        )
    )
    await session.flush()
    return result


async def check_references(session, user, kind, rows):
    errors = []
    for wrapper in rows:
        for target_kind, code, relation in references(kind, wrapper["data"]):
            if await record_by_code(session, user, target_kind, code) is None:
                errors.append(
                    {
                        "row": wrapper["row"],
                        "field": relation,
                        "code": "reference_not_found",
                        "message": f"{target_kind} {code}: not present in this enterprise",
                    }
                )
    return errors


async def stage(
    session, user, kind, filename, source, content_sha, headers, raw, mapping
):
    await lock(session, user)
    normalized, errors = normalize(kind, headers, raw, mapping)
    errors += await check_references(session, user, kind, normalized)
    for r in normalized:
        existing = await record_by_code(session, user, kind, r["data"]["code"])
        if existing and (
            existing.payload != r["data"] or existing.source_type != source
        ):
            errors.append(
                {
                    "row": r["row"],
                    "field": "code",
                    "code": "existing_code_conflict",
                    "message": "Code already exists with different values/source; import never silently overwrites",
                }
            )
    fingerprint = digest(
        [kind, source, content_sha, mapping, errors, now().date().isoformat()]
    )
    old = (
        await session.execute(
            select(ImportBatch).where(
                ImportBatch.tenant_id == user.tenant_id,
                ImportBatch.fingerprint == fingerprint,
            )
        )
    ).scalar_one_or_none()
    if old:
        return {
            **view(old),
            "row_count": len(raw),
            "valid_rows": len(old.rows),
            "preview": old.rows[:10],
            "reused": True,
        }
    batch = ImportBatch(
        tenant_id=user.tenant_id,
        created_by=user.user_id,
        kind=kind,
        filename=filename[:160],
        source_type=source,
        source_sha256=content_sha,
        fingerprint=fingerprint,
        mapping=mapping,
        rows=normalized,
        errors=errors,
        state="invalid" if errors else "validated",
        expires_at=now() + timedelta(hours=24),
    )
    session.add(batch)
    await session.flush()
    await activity(
        session,
        user,
        batch.id,
        "import.previewed",
        {
            "kind": kind,
            "row_count": len(raw),
            "error_count": len(errors),
            "source_type": source,
        },
    )
    return {
        **view(batch),
        "row_count": len(raw),
        "valid_rows": len(normalized),
        "preview": normalized[:10],
        "reused": False,
    }


async def insert_record(session, user, kind, row, source, source_ref, batch_id=None):
    old = await record_by_code(session, user, kind, row["code"])
    if old:
        if old.payload != row or old.source_type != source:
            raise BusinessError(
                "existing_code_conflict",
                "Record exists with different data/source",
                409,
            )
        return old, False
    record = WorkspaceRecord(
        tenant_id=user.tenant_id,
        kind=kind,
        code=row["code"],
        name=row["name"],
        source_type=source,
        source_ref=source_ref,
        import_batch_id=batch_id,
        created_by=user.user_id,
        payload=row,
    )
    session.add(record)
    await session.flush()
    for target_kind, code, relation in references(kind, row):
        target = await record_by_code(session, user, target_kind, code)
        if target is None:
            raise BusinessError(
                "reference_not_found", "Reference not present in this enterprise", 409
            )
        session.add(
            RecordLink(
                tenant_id=user.tenant_id,
                source_id=record.id,
                target_id=target.id,
                relation=relation,
            )
        )
    await activity(
        session,
        user,
        record.id,
        "record.created",
        {
            "kind": kind,
            "code": record.code,
            "source_type": source,
            "import_batch_id": str(batch_id) if batch_id else None,
        },
    )
    await emit(
        session,
        user,
        "record.created",
        record.id,
        {"kind": kind, "code": record.code, "source_type": source},
    )
    return record, True


async def confirm(session, user, batch_id):
    batch = await owned(session, ImportBatch, user, batch_id, True)
    if batch.state == "confirmed":
        count = (
            await session.execute(
                select(func.count())
                .select_from(WorkspaceRecord)
                .where(
                    WorkspaceRecord.tenant_id == user.tenant_id,
                    WorkspaceRecord.import_batch_id == batch.id,
                )
            )
        ).scalar_one()
        return {
            "batch_id": str(batch.id),
            "state": "confirmed",
            "inserted": count,
            "replayed": True,
        }
    if batch.expires_at <= now():
        raise BusinessError(
            "preview_expired",
            "Preview expired; create a fresh preview (next daily window or new content version)",
            410,
        )
    if batch.errors or batch.state != "validated":
        raise BusinessError(
            "preview_invalid", "Preview contains errors; no business rows inserted", 409
        )
    errors = await check_references(session, user, batch.kind, batch.rows)
    if errors:
        raise BusinessError(
            "references_changed",
            "References failed revalidation; transaction not applied",
            409,
        )
    inserted = 0
    for r in batch.rows:
        _, created = await insert_record(
            session,
            user,
            batch.kind,
            r["data"],
            batch.source_type,
            batch.filename,
            batch.id,
        )
        inserted += int(created)
    batch.state = "confirmed"
    batch.confirmed_at = now()
    await activity(
        session,
        user,
        batch.id,
        "import.confirmed",
        {"inserted": inserted, "source_type": batch.source_type},
    )
    await emit(
        session,
        user,
        "import.confirmed",
        batch.id,
        {"kind": batch.kind, "inserted": inserted},
    )
    await session.flush()
    return {
        "batch_id": str(batch.id),
        "state": "confirmed",
        "inserted": inserted,
        "replayed": False,
    }


async def members(session, user):
    users = (
        (
            await session.execute(
                select(User)
                .where(User.tenant_id == user.tenant_id, User.is_active.is_(True))
                .order_by(User.email)
            )
        )
        .scalars()
        .all()
    )
    result = []
    for u in users:
        roles = (
            (
                await session.execute(
                    select(Role.name)
                    .join(UserRole, UserRole.role_id == Role.id)
                    .where(UserRole.user_id == u.id)
                )
            )
            .scalars()
            .all()
        )
        if UserContext(u.id, u.tenant_id, u.email, u.department, list(roles)).is_member:
            result.append({"id": str(u.id), "name": u.full_name, "email": u.email})
    return result


async def assignee(session, user, identifier):
    if identifier is not None and str(identifier) not in {
        r["id"] for r in await members(session, user)
    }:
        raise BusinessError(
            "invalid_assignee", "Assignee must be an active member of this enterprise"
        )


async def create_task(session, user, payload):
    source = await owned(session, WorkspaceRecord, user, payload.record_id)
    await assignee(session, user, payload.assignee_id)
    task = ActionTask(
        tenant_id=user.tenant_id,
        record_id=source.id,
        title=payload.title,
        due_at=payload.due_at,
        assignee_id=payload.assignee_id,
        created_by=user.user_id,
        measures=payload.measures,
    )
    session.add(task)
    await session.flush()
    await activity(
        session,
        user,
        task.id,
        "task.created",
        {"after": view(task), "source_type": source.source_type},
    )
    await emit(
        session,
        user,
        "task.created",
        task.id,
        {"state": task.state, "version": task.version},
    )
    return view(task)


async def change_task(session, user, identifier, payload):
    task = await owned(session, ActionTask, user, identifier, True)
    if task.version != payload.expected_version:
        raise BusinessError(
            "version_conflict", "Task changed; reload and review before retrying", 409
        )
    before = view(task)
    transitions = {
        "start": ("open", "in_progress"),
        "submit": ("in_progress", "pending_verification"),
        "complete": ("pending_verification", "completed"),
        "reopen": ("pending_verification", "in_progress"),
    }
    if payload.action == "assign":
        if task.state in {"completed", "cancelled"}:
            raise BusinessError(
                "invalid_transition", "Closed task cannot be reassigned", 409
            )
        await assignee(session, user, payload.assignee_id)
        task.assignee_id = payload.assignee_id
    elif payload.action == "cancel":
        if (
            task.state in {"completed", "cancelled"}
            or not (payload.result or "").strip()
        ):
            raise BusinessError(
                "invalid_transition",
                "Cancellation requires an open task and reason",
                409,
            )
        task.state = "cancelled"
    else:
        old, new = transitions[payload.action]
        if task.state != old:
            raise BusinessError(
                "invalid_transition", "State transition is not allowed", 409
            )
        if payload.action == "start" and (
            not task.assignee_id or not (payload.measures or task.measures).strip()
        ):
            raise BusinessError(
                "missing_execution_details",
                "Assign an owner and specify measures before starting",
            )
        if (
            payload.action in {"submit", "complete", "reopen"}
            and not (payload.result or "").strip()
        ):
            raise BusinessError(
                "missing_result", "Verification/rework requires a result or reason"
            )
        if payload.action == "submit" and payload.actual_cost_cny is None:
            raise BusinessError(
                "missing_actual_cost",
                "Submit an explicit actual cost, including zero when applicable",
            )
        task.state = new
    if payload.measures is not None:
        task.measures = payload.measures
    if payload.actual_cost_cny is not None:
        task.actual_cost_cny = f"{payload.actual_cost_cny:.2f}"
    if payload.result is not None:
        task.result = payload.result
    task.version += 1
    await session.flush()
    await session.refresh(task)
    await activity(
        session,
        user,
        task.id,
        "task.updated",
        {"command": payload.action, "before": before, "after": view(task)},
    )
    await emit(
        session,
        user,
        "task.updated",
        task.id,
        {"state": task.state, "version": task.version},
    )
    return view(task)


async def demo_scenario(session, user, scenario_id):
    from packages.business.dataset import load_dataset

    d = load_dataset()
    scenario = next((s for s in d.scenarios if s.id == scenario_id), None)
    if not scenario:
        raise BusinessError("unknown_scenario", "Unknown demo scenario", 404)
    for site in d.sites:
        await insert_record(
            session,
            user,
            "site",
            {
                "code": site.id,
                "name": site.name,
                "site_type": site.kind,
                "latitude": site.latitude,
                "longitude": site.longitude,
                "country": site.country,
            },
            "synthetic",
            d.dataset_version,
        )
    for order in d.orders:
        row = {
            "code": order.id,
            "name": order.name,
            "destination_site_code": order.destination_site_id,
            "product_code": order.product_id,
            "customer": order.customer,
            "amount_cny": str(order.amount_cny),
            "currency": "CNY",
            "promised_at": order.promised_at.isoformat(),
            "status": order.status,
        }
        row = ROWS["order"].model_validate(row).model_dump(mode="json")
        await insert_record(session, user, "order", row, "synthetic", d.dataset_version)
    for shipment in d.shipments:
        row = {
            "code": shipment.id,
            "name": shipment.name,
            "origin_site_code": shipment.origin_site_id,
            "destination_site_code": shipment.destination_site_id,
            "order_codes": ";".join(shipment.order_ids),
            "mode": shipment.mode,
            "eta": shipment.eta.isoformat(),
        }
        await insert_record(
            session, user, "shipment", row, "synthetic", d.dataset_version
        )
    ids = []
    for event in d.risk_events:
        if event.id not in scenario.risk_event_ids:
            continue
        row = {
            "code": event.id,
            "name": event.name,
            "site_codes": ";".join(event.site_ids),
            "order_codes": ";".join(event.affected_order_ids),
            "severity": event.severity,
            "description": event.description,
            "detected_at": event.detected_at.isoformat(),
        }
        r, _ = await insert_record(
            session, user, "event", row, "synthetic", d.dataset_version
        )
        ids.append(view(r))
    return {"scenario_id": scenario_id, "source_type": "synthetic", "events": ids}


async def capture(session, user, payload):
    if payload.kind == "simulation":
        from packages.business.simulation_store import read_snapshot

        try:
            artifact = read_snapshot(user, payload.identifier)
        except (KeyError, PermissionError, ValueError) as exc:
            raise BusinessError(
                "snapshot_not_found",
                "Only your own simulation snapshots may be explicitly shared",
                404,
            ) from exc
        source = "synthetic"
        body = {
            "code": "SIM-" + payload.identifier,
            "name": "已共享模拟快照 " + payload.identifier[:12],
            "artifact": artifact,
            "shared_by": str(user.user_id),
            "assumptions": "Synthetic simulation, not actual savings or prediction accuracy",
        }
    else:
        from packages.prediction.runtime import predict

        try:
            artifact = predict(payload.identifier, "dataco-retail-historical")
        except (KeyError, ValueError, FileNotFoundError) as exc:
            raise BusinessError(
                "prediction_unavailable", "Historical prediction is unavailable", 422
            ) from exc
        source = "public_historical"
        body = {
            "code": "PRED-"
            + payload.identifier
            + "-"
            + digest(artifact["model_version"])[:12],
            "name": "公开历史预测 " + payload.identifier[:12],
            "artifact": artifact,
            "domain": "dataco-retail-historical",
            "assumptions": "No validated manufacturing transfer",
        }
    # The explicit share instruction creates a tenant business copy; old private files are unchanged.
    old = await record_by_code(session, user, payload.kind, body["code"])
    if old:
        return view(old)
    record = WorkspaceRecord(
        tenant_id=user.tenant_id,
        kind=payload.kind,
        code=body["code"],
        name=body["name"],
        source_type=source,
        source_ref=payload.identifier,
        created_by=user.user_id,
        payload=body,
    )
    session.add(record)
    await session.flush()
    await activity(
        session,
        user,
        record.id,
        "record.created",
        {"kind": record.kind, "source_type": source, "explicit_tenant_share": True},
    )
    await emit(
        session,
        user,
        "record.created",
        record.id,
        {"kind": record.kind, "source_type": source},
    )
    return view(record)
