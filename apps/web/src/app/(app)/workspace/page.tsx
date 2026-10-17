"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  getWorkspace,
  sendWorkspace,
  useCommand,
  downloadWorkspace,
  workspaceError,
  kinds,
  sources,
  Entity,
  Batch,
  Report,
  Page,
  Subscription,
} from "@/lib/workspace";
const card = "rounded-2xl border border-slate-200 bg-white p-5";
const button =
  "rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white disabled:opacity-40";
const input =
  "mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-sm";
export default function WorkspacePage() {
  const qc = useQueryClient();
  const [tab, setTab] = useState("records");
  const [kind, setKind] = useState("site");
  const [source, setSource] = useState("enterprise_uploaded");
  const [file, setFile] = useState<File | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [headers, setHeaders] = useState<string[]>([]);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState<Entity | null>(null);
  const [events, setEvents] = useState<
    { id: number; topic: string; resource_id: string; payload: unknown }[]
  >([]);
  const [cursor, setCursor] = useState(0);
  const [activeSub, setActiveSub] = useState("");
  const schema = useQuery({
    queryKey: ["workspace-schema"],
    queryFn: () =>
      getWorkspace<{ fields: Record<string, string[]> }>("/schema"),
  });
  const records = useQuery({
    queryKey: ["workspace-records", kind, q, offset],
    queryFn: () =>
      getWorkspace<Page<Entity>>(
        `/records?kind=${kind}&q=${encodeURIComponent(q)}&offset=${offset}&limit=20`,
      ),
  });
  const imports = useQuery({
    queryKey: ["workspace-imports"],
    queryFn: () => getWorkspace<Page<Batch>>("/imports"),
  });
  const reports = useQuery({
    queryKey: ["workspace-reports"],
    queryFn: () => getWorkspace<Page<Report>>("/reports"),
  });
  const subs = useQuery({
    queryKey: ["workspace-subscriptions"],
    queryFn: () => getWorkspace<Page<Subscription>>("/subscriptions"),
  });
  const refresh = () =>
    qc.invalidateQueries({ queryKey: ["workspace-records"] });
  const inspect = useMutation({
    mutationFn: async () => {
      if (!file) throw Error();
      const f = new FormData();
      f.append("file", file);
      return sendWorkspace<{ headers: string[] }>(
        "/imports/inspect",
        f,
        crypto.randomUUID(),
      );
    },
    onSuccess: (data) => {
      setHeaders(data.headers);
      setMapping(
        Object.fromEntries(
          (schema.data?.fields[kind] || [])
            .filter((f) => data.headers.includes(f))
            .map((f) => [f, f]),
        ),
      );
      setBatch(null);
    },
  });
  const preview = useCommand<
    Batch,
    {
      intent: string;
      fileName: string;
      size: number;
      modified: number;
      mapping: Record<string, string>;
      kind: string;
      source: string;
    }
  >(async (value, key) => {
    if (!file) throw Error();
    const f = new FormData();
    f.append("file", file);
    f.append("kind", value.kind);
    f.append("source_type", value.source);
    f.append("mapping", JSON.stringify(value.mapping));
    return sendWorkspace("/imports/preview", f, key);
  });
  const confirm = useCommand<{ inserted: number }, string>((id, key) =>
    sendWorkspace("/imports/" + id + "/confirm", {}, key),
  );
  const archive = useCommand<{ events: Entity[] }, string>((scenario_id, key) =>
    sendWorkspace("/demo-scenario", { scenario_id }, key),
  );
  const report = useCommand<
    Report,
    { kind: string; format: string; intent: string }
  >(({ intent, ...body }, key) => sendWorkspace("/reports", body, key));
  const subscribe = useCommand<Subscription, string>((name, key) =>
    sendWorkspace(
      "/subscriptions",
      {
        name,
        topics: [
          "task.created",
          "task.updated",
          "import.confirmed",
          "report.created",
        ],
      },
      key,
    ),
  );
  async function download(path: string, name: string) {
    try {
      await downloadWorkspace(path, name);
    } catch (e) {
      setMessage(workspaceError(e));
    }
  }
  async function poll(id: string, after: number) {
    try {
      const data = await getWorkspace<{
        items: typeof events;
        next_cursor: number;
      }>(`/subscriptions/${id}/events?after=${after}`);
      setEvents(data.items);
      setCursor(data.next_cursor);
      setActiveSub(id);
    } catch (e) {
      setMessage(workspaceError(e));
    }
  }
  const errors = [inspect, preview, confirm, archive, report, subscribe].filter(
    (m) => m.isError,
  );
  return (
    <div className="space-y-5" data-testid="workspace-page">
      <PageHeader
        title="企业数据工作区"
        description="把数据、处置记录和可复核报告留在本企业，让每一次判断有来源、每一项措施有结果。"
      />
      <button
        className="self-start text-sm text-indigo-600"
        onClick={() =>
          download("/openapi", "supplyguard-enterprise-openapi.json")
        }
      >
        下载企业API说明（OpenAPI）
      </button>
      <div className="rounded-2xl bg-slate-900 p-5 text-sm leading-6 text-slate-200">
        <p className="font-semibold text-white">
          本企业共享 · 数据来源独立标识
        </p>
        <p className="mt-2">
          上传内容仅在预检确认后保存，不会覆盖现有记录。模拟控制塔继续使用演示数据；企业上传数据可在这里关联任务与导出报告，尚未接入实时ERP或制造预测模型。
        </p>
      </div>
      <nav aria-label="数据工作区功能" className="flex flex-wrap gap-2">
        {[
          ["records", "企业记录"],
          ["imports", "导入与预检"],
          ["reports", "报告中心"],
          ["events", "本地事件订阅"],
        ].map(([id, label]) => (
          <button
            key={id}
            onClick={() => {
              setTab(id);
              setMessage("");
            }}
            aria-pressed={tab === id}
            className={`rounded-lg px-4 py-2 text-sm ${tab === id ? "bg-slate-900 text-white" : "border bg-white text-slate-500"}`}
          >
            {label}
          </button>
        ))}
      </nav>
      {message && (
        <p
          role="status"
          className="rounded-xl bg-teal-50 p-3 text-sm text-teal-800"
        >
          {message}
        </p>
      )}
      {errors.map((m, i) => (
        <p
          key={i}
          role="alert"
          className="rounded-xl bg-red-50 p-3 text-sm text-red-700"
        >
          {workspaceError(m.error)}
        </p>
      ))}
      {tab === "records" && (
        <section className={card}>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-semibold">企业业务记录</h2>
              <p className="mt-2 text-xs text-slate-500">
                按站点→订单→批次/风险事件顺序导入；归档预测与模拟保留各自适用范围。
              </p>
            </div>
            <button
              className="rounded-lg border px-3 py-2 text-xs"
              disabled={archive.isPending}
              onClick={async () => {
                const r = await archive
                  .mutateAsync("port-congestion")
                  .catch(() => null);
                if (r) {
                  setKind("event");
                  setOffset(0);
                  refresh();
                  setMessage(
                    "港口场景已保存为模拟来源，可创建企业共享处置任务。",
                  );
                }
              }}
            >
              保存港口演示场景
            </button>
          </div>
          <div className="mt-4 flex flex-wrap gap-3">
            <select
              aria-label="记录类型"
              value={kind}
              onChange={(e) => {
                setKind(e.target.value);
                setOffset(0);
                setSelected(null);
              }}
              className="rounded-lg border p-2 text-sm"
            >
              {Object.entries(kinds).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
            <input
              aria-label="搜索企业记录"
              placeholder="搜索编号或名称"
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setOffset(0);
              }}
              className="rounded-lg border p-2 text-sm"
            />
          </div>
          {records.isError && (
            <p role="alert" className="mt-4 text-red-600">
              记录读取失败。
              <button onClick={() => records.refetch()}>重试</button>
            </p>
          )}
          <div className="mt-4 divide-y">
            {records.data?.items.map((r) => (
              <div
                key={r.id}
                className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm"
              >
                <div>
                  <button
                    className="font-medium text-indigo-600"
                    onClick={() => setSelected(r)}
                  >
                    {r.name}
                  </button>
                  <p className="mt-1 text-xs text-slate-400">
                    {r.code} · {sources[r.source_type]}
                  </p>
                </div>
                <Link
                  className="rounded-lg border px-3 py-2 text-xs"
                  href={"/actions?record_id=" + r.id}
                >
                  创建处置任务
                </Link>
              </div>
            ))}
            {records.data?.total === 0 && (
              <p className="py-10 text-sm text-slate-400">
                暂无此类记录。可先导入文件，或保存一组标注清楚的演示场景。
              </p>
            )}
          </div>
          <div className="mt-4 flex gap-4 text-xs">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              上一页
            </button>
            <span>
              共 {records.data?.total || 0} 条 · 第 {offset / 20 + 1} 页
            </span>
            <button
              disabled={offset + 20 >= (records.data?.total || 0)}
              onClick={() => setOffset(offset + 20)}
            >
              下一页
            </button>
          </div>
          {selected && (
            <div className="mt-5 rounded-xl bg-slate-50 p-4">
              <div className="flex justify-between">
                <h3 className="text-sm font-medium">记录与来源明细</h3>
                <button className="text-xs" onClick={() => setSelected(null)}>
                  关闭明细
                </button>
              </div>
              <p className="mt-2 break-all text-xs text-slate-400">
                来源 {selected.source_ref} · 导入批次{" "}
                {selected.import_batch_id || "直接归档"}
              </p>
              <pre className="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-all text-xs text-slate-600">
                {JSON.stringify(selected.payload, null, 2)}
              </pre>
            </div>
          )}
        </section>
      )}
      {tab === "imports" && (
        <section className={card}>
          <h2 className="font-semibold">先预检，再确认导入</h2>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            UTF-8 CSV或单表XLSX，最多2 MiB /
            1,000行。时间需带时区，金额为人民币；多引用用分号分隔。错误行不会部分入库，现有编号内容不同会拒绝覆盖。
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-3">
            <label className="text-sm">
              导入对象
              <select
                aria-label="导入对象"
                value={kind in (schema.data?.fields || {}) ? kind : "site"}
                onChange={(e) => {
                  setKind(e.target.value);
                  setHeaders([]);
                  setMapping({});
                  setBatch(null);
                }}
                className={input}
              >
                {["site", "order", "shipment", "event"].map((k) => (
                  <option key={k} value={k}>
                    {kinds[k]}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              内容来源
              <select
                aria-label="内容来源"
                value={source}
                onChange={(e) => {
                  setSource(e.target.value);
                  setBatch(null);
                }}
                className={input}
              >
                <option value="enterprise_uploaded">
                  企业上传 · 未经外部核验
                </option>
                <option value="synthetic">模拟数据</option>
              </select>
            </label>
            <div className="flex items-end gap-2">
              {["csv", "xlsx"].map((f) => (
                <button
                  key={f}
                  onClick={() =>
                    download(
                      `/templates/${kind in (schema.data?.fields || {}) ? kind : "site"}?format=${f}`,
                      `${kind}-template.${f}`,
                    )
                  }
                  className="rounded-lg border px-3 py-2 text-xs"
                >
                  下载{f.toUpperCase()}模板
                </button>
              ))}
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <label className="text-sm">
              数据文件
              <input
                aria-label="数据文件"
                type="file"
                accept=".csv,.xlsx"
                onChange={(e) => {
                  setFile(e.target.files?.[0] || null);
                  setHeaders([]);
                  setBatch(null);
                  inspect.reset();
                  preview.reset();
                  confirm.reset();
                }}
                className="mt-2 block max-w-full text-xs"
              />
            </label>
            <button
              className={button}
              disabled={!file || inspect.isPending}
              onClick={() => inspect.mutate()}
            >
              读取表头
            </button>
          </div>
          {headers.length > 0 && (
            <>
              <h3 className="mt-5 text-sm font-medium">字段映射</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {(schema.data?.fields[kind] || []).map((field) => (
                  <label key={field} className="text-xs text-slate-500">
                    {field}
                    <select
                      aria-label={"映射 " + field}
                      className={input}
                      value={mapping[field] || ""}
                      onChange={(e) => {
                        setMapping({ ...mapping, [field]: e.target.value });
                        setBatch(null);
                      }}
                    >
                      <option value="">未映射 / 使用默认值</option>
                      {headers.map((h) => (
                        <option key={h}>{h}</option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <button
                className={button + " mt-4"}
                disabled={preview.isPending || !file}
                onClick={async () => {
                  if (!file) return;
                  const b = await preview
                    .mutateAsync({
                      intent: crypto.randomUUID(),
                      fileName: file.name,
                      size: file.size,
                      modified: file.lastModified,
                      mapping: Object.fromEntries(
                        Object.entries(mapping).filter(([, v]) => v),
                      ),
                      kind,
                      source,
                    })
                    .catch(() => null);
                  if (b) setBatch(b);
                }}
              >
                运行预检
              </button>
            </>
          )}
          {batch && (
            <div
              className="mt-5 rounded-xl border p-4"
              data-testid="import-preview"
            >
              <p className="text-sm font-medium">
                {batch.state === "confirmed"
                  ? "此批次已导入"
                  : batch.errors.length
                    ? "预检有错误，禁止确认"
                    : "预检通过，尚未入库"}{" "}
                · {batch.row_count} 行
              </p>
              <p className="mt-2 break-all text-[10px] text-slate-400">
                批次 {batch.id} · 原文件SHA256 {batch.source_sha256}
              </p>
              {batch.errors.length > 0 && (
                <div className="mt-3 max-h-72 overflow-auto text-xs text-red-700">
                  {batch.errors.map((e, i) => (
                    <p key={i} className="py-1">
                      第{e.row}行 · {e.field} · {e.code}：{e.message}
                    </p>
                  ))}
                </div>
              )}
              <details className="mt-3 text-xs">
                <summary>查看规范化前10行预览</summary>
                <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all">
                  {JSON.stringify(batch.preview, null, 2)}
                </pre>
              </details>
              <button
                className={button + " mt-4"}
                disabled={
                  !!batch.errors.length ||
                  batch.state === "confirmed" ||
                  confirm.isPending
                }
                onClick={async () => {
                  const r = await confirm
                    .mutateAsync(batch.id)
                    .catch(() => null);
                  if (r) {
                    setBatch({ ...batch, state: "confirmed" });
                    setMessage(
                      `确认导入完成，新增 ${r.inserted} 条；重复确认不会重复新增。`,
                    );
                    refresh();
                    qc.invalidateQueries({ queryKey: ["workspace-imports"] });
                  }
                }}
              >
                确认导入本企业
              </button>
            </div>
          )}
          <h3 className="mt-6 text-sm font-medium">最近导入批次</h3>
          {imports.data?.items.map((b) => (
            <div
              key={b.id}
              className="mt-2 flex flex-wrap justify-between gap-2 rounded-lg bg-slate-50 p-3 text-xs"
            >
              <span>
                {b.filename} · {kinds[b.kind]} · {sources[b.source_type]}
              </span>
              <span>
                {
                  (
                    {
                      validated: "待确认",
                      invalid: "预检错误",
                      confirmed: "已导入",
                    } as Record<string, string>
                  )[b.state]
                }{" "}
                · {b.errors.length} 个错误
              </span>
            </div>
          ))}
        </section>
      )}
      {tab === "reports" && (
        <section className={card}>
          <h2 className="font-semibold">报告中心</h2>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            风险报告按事件关联的唯一未交付订单计算敞口；人工填报费用、模拟数据与公开评测分别标注。下载需登录同一企业，有效期24小时；过期后可重新生成。
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {[
              ["risk", "风险报告"],
              ["evaluation", "公开评测报告"],
            ].map(([k, label]) =>
              ["xlsx", "csv"].map((f) => (
                <button
                  key={k + f}
                  disabled={report.isPending}
                  className={button}
                  onClick={async () => {
                    const r = await report
                      .mutateAsync({
                        kind: k,
                        format: f,
                        intent: crypto.randomUUID(),
                      })
                      .catch(() => null);
                    if (r) {
                      qc.invalidateQueries({ queryKey: ["workspace-reports"] });
                      setMessage(`${label}已生成，含来源和校验哈希。`);
                    }
                  }}
                >
                  {label} {f.toUpperCase()}
                </button>
              )),
            )}
          </div>
          <div className="mt-5 space-y-3">
            {reports.data?.items.map((r) => (
              <div
                key={r.id}
                data-testid={"workspace-report-" + r.id}
                className="rounded-xl border p-4 text-xs"
              >
                <div className="flex flex-wrap justify-between gap-3">
                  <span className="font-medium">
                    {r.kind === "risk" ? "风险报告" : "评测报告"} ·{" "}
                    {r.format.toUpperCase()}
                  </span>
                  <button
                    className="text-indigo-600"
                    onClick={() =>
                      download("/reports/" + r.id + "/download", r.filename)
                    }
                  >
                    下载报告
                  </button>
                </div>
                <p className="mt-2 text-slate-500">
                  {r.kind === "risk"
                    ? `风险敞口 ¥${r.summary.exposure_amount_cny || "0.00"} · ${r.summary.unique_at_risk_orders || 0} 笔唯一订单`
                    : "公开历史或明确标注的历史评测，不代表制造业准确率"}
                </p>
                <p className="mt-2 break-all text-slate-400">
                  有效至 {new Date(r.expires_at).toLocaleString("zh-CN")} ·
                  SHA256 {r.sha256}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
      {tab === "events" && (
        <section className={card}>
          <h2 className="font-semibold">本地事件订阅</h2>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            任务变更、导入确认、报告生成与业务事务一起保存。可按游标读取和重放；不会外发邮件、消息或Webhook，也不会自动执行采购。
          </p>
          <button
            className={button + " mt-4"}
            disabled={subscribe.isPending}
            onClick={async () => {
              const r = await subscribe
                .mutateAsync("企业处置动态")
                .catch(() => null);
              if (r) {
                qc.invalidateQueries({ queryKey: ["workspace-subscriptions"] });
                setActiveSub(r.id);
                setCursor(0);
                setMessage("本地订阅已创建，可读取已有和后续事件。");
              }
            }}
          >
            创建本地订阅
          </button>
          <div className="mt-4 flex flex-wrap gap-3">
            <select
              aria-label="本地订阅"
              value={activeSub}
              onChange={(e) => {
                setActiveSub(e.target.value);
                setCursor(0);
                setEvents([]);
              }}
              className="rounded-lg border p-2 text-sm"
            >
              <option value="">选择订阅</option>
              {subs.data?.items.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} · {s.id.slice(0, 8)}
                </option>
              ))}
            </select>
            <button
              className="rounded-lg border px-3 py-2 text-sm"
              disabled={!activeSub}
              onClick={() => poll(activeSub, cursor)}
            >
              读取后续事件
            </button>
            <button
              className="rounded-lg border px-3 py-2 text-sm"
              disabled={!activeSub}
              onClick={() => poll(activeSub, 0)}
            >
              从头重放
            </button>
          </div>
          <p className="mt-3 text-xs text-slate-400">
            当前游标 {cursor} · 仅本地保存，外发数量0
          </p>
          {events.map((e) => (
            <div key={e.id} className="mt-3 rounded-lg bg-slate-50 p-3 text-xs">
              <p>
                #{e.id} · {e.topic}
              </p>
              <p className="mt-1 break-all text-slate-400">
                业务对象 {e.resource_id}
              </p>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
