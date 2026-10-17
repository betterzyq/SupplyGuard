"""Real immutable report bytes, tenant ownership, digest and 24-hour expiry."""

from datetime import timedelta
from decimal import Decimal
import hashlib
import json
import uuid
from sqlalchemy import select
from packages.common.db.models.workspace import (
    WorkspaceRecord,
    RecordLink,
    ActionTask,
    WorkspaceReport,
)
from .files import csv_bytes, workbook_bytes
from .service import now, activity, emit, view, BusinessError


async def create_report(session, user, request):
    summary = {
        "source": "tenant_business_workspace",
        "generated_at": now().isoformat(),
        "tenant_id": str(user.tenant_id),
        "scope": "本企业工作区；不合并旧技术图谱或个人模拟文件",
        "amount_definition": "唯一关联未交付/未取消订单的风险敞口；不是预计损失或实际收益",
    }
    if request.kind == "risk":
        records = (
            (
                await session.execute(
                    select(WorkspaceRecord)
                    .where(WorkspaceRecord.tenant_id == user.tenant_id)
                    .order_by(WorkspaceRecord.kind, WorkspaceRecord.code)
                    .limit(10001)
                )
            )
            .scalars()
            .all()
        )
        if len(records) > 10000:
            raise BusinessError(
                "export_limit", "Export limited to 10000 records; partition the dataset"
            )
        records_by_id = {r.id: r for r in records}
        links = (
            (
                await session.execute(
                    select(RecordLink).where(
                        RecordLink.tenant_id == user.tenant_id,
                        RecordLink.relation == "affects",
                    )
                )
            )
            .scalars()
            .all()
        )
        order_ids = {
            link.target_id
            for link in links
            if link.source_id in records_by_id
            and records_by_id[link.source_id].kind == "event"
        }
        orders = [
            r
            for r in records
            if r.kind == "order"
            and r.id in order_ids
            and r.payload["status"] not in {"delivered", "cancelled"}
        ]
        events = [r for r in records if r.kind == "event"]
        tasks = (
            (
                await session.execute(
                    select(ActionTask)
                    .where(ActionTask.tenant_id == user.tenant_id)
                    .order_by(ActionTask.created_at, ActionTask.id)
                    .limit(10001)
                )
            )
            .scalars()
            .all()
        )
        if len(tasks) > 10000:
            raise BusinessError("export_limit", "Export limited to 10000 tasks")
        summary.update(
            unique_at_risk_orders=len(orders),
            events=len(events),
            exposure_amount_cny=f'{sum((Decimal(r.payload["amount_cny"]) for r in orders),Decimal(0)):.2f}',
            currency="CNY",
            source_types=sorted({r.source_type for r in records}),
            actual_task_cost_cny=f"{sum((Decimal(t.actual_cost_cny) for t in tasks),Decimal(0)):.2f}",
            actual_cost_definition="人工填报费用，不代表系统验证的财务实付，不与仿真成本混算",
        )
        sheets = {
            "Orders": [
                [
                    "code",
                    "name",
                    "amount_cny",
                    "status",
                    "source_type",
                    "import_batch_id",
                    "source_ref",
                ]
            ]
            + [
                [
                    r.code,
                    r.name,
                    r.payload["amount_cny"],
                    r.payload["status"],
                    r.source_type,
                    str(r.import_batch_id or ""),
                    r.source_ref,
                ]
                for r in orders
            ],
            "Events": [["code", "name", "severity", "source_type", "order_codes"]]
            + [
                [
                    r.code,
                    r.name,
                    r.payload["severity"],
                    r.source_type,
                    r.payload["order_codes"],
                ]
                for r in events
            ],
            "Actions": [
                [
                    "id",
                    "title",
                    "state",
                    "version",
                    "record_id",
                    "source_type",
                    "assignee_id",
                    "due_at",
                    "actual_cost_cny",
                    "measures",
                    "result",
                ]
            ]
            + [
                [
                    str(t.id),
                    t.title,
                    t.state,
                    t.version,
                    str(t.record_id),
                    records_by_id[t.record_id].source_type,
                    str(t.assignee_id or ""),
                    t.due_at.isoformat(),
                    t.actual_cost_cny,
                    t.measures,
                    t.result,
                ]
                for t in tasks
            ],
            "Lineage": [
                ["kind", "code", "source_type", "source_ref", "import_batch_id"]
            ]
            + [
                [
                    r.kind,
                    r.code,
                    r.source_type,
                    r.source_ref,
                    str(r.import_batch_id or ""),
                ]
                for r in records
            ],
        }
    else:
        if request.benchmark_run_id:
            if not user.is_admin:
                raise BusinessError(
                    "admin_required", "Historical benchmark exports require admin", 403
                )
            from packages.common.db.models.benchmark import (
                BenchmarkRun,
                BenchmarkResult,
            )

            run = (
                await session.execute(
                    select(BenchmarkRun).where(
                        BenchmarkRun.tenant_id == user.tenant_id,
                        BenchmarkRun.id == request.benchmark_run_id,
                    )
                )
            ).scalar_one_or_none()
            if not run:
                raise BusinessError("not_found", "Benchmark not found", 404)
            rows = (
                (
                    await session.execute(
                        select(BenchmarkResult)
                        .where(BenchmarkResult.benchmark_run_id == run.id)
                        .limit(10001)
                    )
                )
                .scalars()
                .all()
            )
            if len(rows) > 10000:
                raise BusinessError(
                    "export_limit", "Historical report exceeds 10000 rows"
                )
            summary.update(
                source="historical_benchmark",
                warning="历史岗位金标准口径已废弃；不代表enterprise-v2、风险模型准确率或当前检索质量",
                benchmark_run_id=str(run.id),
                run_status=run.status,
            )
            sheets = {
                "Results": [["question_id", "question", "metrics_json", "error"]]
                + [
                    [
                        r.question_id,
                        r.question,
                        json.dumps(r.metrics, ensure_ascii=False),
                        r.error or "",
                    ]
                    for r in rows
                ]
            }
        else:
            from packages.prediction.runtime import report

            try:
                r = report()
            except (FileNotFoundError, ValueError) as exc:
                raise BusinessError(
                    "evaluation_unavailable",
                    "Validated public experiment unavailable",
                    503,
                ) from exc
            summary.update(
                source="public_historical",
                domain=r["domain"],
                model_version=r["model_version"],
                protocol_sha256=r["protocol_sha256"],
                source_sha256=r["source_sha256"],
                warning="仅DataCo公开历史验证；制造业迁移未验证；AP不是准确率或收益",
            )
            sheets = {
                "Models": [
                    [
                        "model",
                        "test_orders",
                        "average_precision",
                        "recall_top10",
                        "precision_top10",
                        "late_amount_capture",
                        "brier",
                    ]
                ]
                + [
                    [
                        name,
                        x["test"]["count"],
                        x["test"]["average_precision"],
                        x["test"]["ranking"]["10"]["recall"],
                        x["test"]["ranking"]["10"]["precision"],
                        x["test"]["ranking"]["10"]["late_quoted_amount_capture"],
                        x["test"].get("brier"),
                    ]
                    for name, x in r["models"].items()
                ],
                "Failures": [["case_id", "kind", "probability", "observed_label"]]
                + [
                    [f["case_id"], f["kind"], f["probability"], f["label"]]
                    for f in r["failure_cases"]
                ],
            }
    summary_rows = [["field", "value"]] + [
        [
            k,
            (
                json.dumps(v, ensure_ascii=False)
                if isinstance(v, (dict, list))
                else str(v)
            ),
        ]
        for k, v in summary.items()
    ]
    sheets = {"Summary": summary_rows, **sheets}
    if request.format == "xlsx":
        content = workbook_bytes(sheets)
    else:
        flat = [["section", "row_json"]]
        for name, rows in sheets.items():
            columns = rows[0]
            flat.extend(
                [
                    [name, json.dumps(dict(zip(columns, row)), ensure_ascii=False)]
                    for row in rows[1:]
                ]
            )
        content = csv_bytes(flat)
    if len(content) > 10 * 1024 * 1024:
        raise BusinessError("export_limit", "Generated report exceeds 10 MiB")
    identifier = uuid.uuid4()
    record = WorkspaceReport(
        id=identifier,
        tenant_id=user.tenant_id,
        created_by=user.user_id,
        kind=request.kind,
        format=request.format,
        filename=f"{request.kind}-report-{identifier}.{request.format}",
        content=content,
        sha256=hashlib.sha256(content).hexdigest(),
        summary=summary,
        expires_at=now() + timedelta(hours=24),
    )
    session.add(record)
    await session.flush()
    await activity(
        session,
        user,
        identifier,
        "report.created",
        {
            "kind": request.kind,
            "format": request.format,
            "sha256": record.sha256,
            "summary": summary,
        },
    )
    await emit(
        session,
        user,
        "report.created",
        identifier,
        {"kind": request.kind, "sha256": record.sha256},
    )
    return {
        **view(record),
        "download_url": f"/api/v1/workspace/reports/{identifier}/download",
        "status": "ready",
    }
