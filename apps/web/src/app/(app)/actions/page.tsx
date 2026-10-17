"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getWorkspace,
  sendWorkspace,
  useCommand,
  workspaceError,
  states,
  sources,
  Entity,
  Task,
  Page,
} from "@/lib/workspace";
const card = "rounded-2xl border border-slate-200 bg-white p-5";
const field = "mt-1 w-full rounded-lg border border-slate-200 p-2 text-sm";
const button =
  "rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white disabled:opacity-40";
export default function ActionsPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [sourceQuery, setSourceQuery] = useState("");
  const [selected, setSelected] = useState("");
  const [recordId, setRecordId] = useState("");
  const [title, setTitle] = useState("");
  const [due, setDue] = useState("");
  const [owner, setOwner] = useState("");
  const [draftOwner, setDraftOwner] = useState("");
  const [draftMeasures, setDraftMeasures] = useState("");
  const [measures, setMeasures] = useState("");
  const [cost, setCost] = useState("0.00");
  const [result, setResult] = useState("");
  const [scenario, setScenario] = useState("port-congestion");
  const [requestedEvent, setRequestedEvent] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    setRecordId(p.get("record_id") || "");
    setRequestedEvent(p.get("demo_event") || "");
    setScenario(p.get("scenario") || "port-congestion");
    const d = new Date(Date.now() + 2 * 86400000);
    setDue(
      new Date(d.getTime() - d.getTimezoneOffset() * 60000)
        .toISOString()
        .slice(0, 16),
    );
  }, []);
  const tasks = useQuery({
    queryKey: ["workspace-tasks", filter, offset],
    queryFn: () =>
      getWorkspace<Page<Task>>(
        `/tasks?limit=20&offset=${offset}${filter ? "&state=" + filter : ""}`,
      ),
  });
  const records = useQuery({
    queryKey: ["workspace-source-options", sourceQuery],
    queryFn: () =>
      getWorkspace<Page<Entity>>(
        "/records?limit=100&q=" + encodeURIComponent(sourceQuery),
      ),
  });
  const requestedSource = useQuery({
    queryKey: ["workspace-requested-source", recordId],
    queryFn: () => getWorkspace<Entity>("/records/" + recordId),
    enabled: !!recordId,
  });
  const members = useQuery({
    queryKey: ["workspace-members"],
    queryFn: () =>
      getWorkspace<{ items: { id: string; name: string; email: string }[] }>(
        "/members",
      ),
  });
  const focused = useQuery({
    queryKey: ["workspace-task", selected],
    queryFn: () => getWorkspace<Task>("/tasks/" + selected),
    enabled: !!selected,
    refetchOnWindowFocus: false,
  });
  const history = useQuery({
    queryKey: ["workspace-history", selected],
    queryFn: () =>
      getWorkspace<
        Page<{
          id: string;
          action: string;
          detail: Record<string, unknown>;
          created_at: string;
        }>
      >("/tasks/" + selected + "/history"),
    enabled: !!selected,
  });
  const source = useQuery({
    queryKey: ["workspace-task-source", focused.data?.record_id],
    queryFn: () => getWorkspace<Entity>("/records/" + focused.data!.record_id),
    enabled: !!focused.data,
  });
  const create = useCommand<
    Task,
    {
      record_id: string;
      title: string;
      due_at: string;
      assignee_id: string | null;
      measures: string;
    }
  >((body, key) => sendWorkspace("/tasks", body, key));
  const change = useCommand<
    Task,
    {
      id: string;
      expected_version: number;
      action: string;
      assignee_id?: string | null;
      measures?: string;
      result?: string;
      actual_cost_cny?: string;
    }
  >(({ id, ...body }, key) =>
    sendWorkspace("/tasks/" + id, body, key, "patch"),
  );
  const archive = useCommand<{ events: Entity[] }, string>((scenario_id, key) =>
    sendWorkspace("/demo-scenario", { scenario_id }, key),
  );
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["workspace-tasks"] });
    qc.invalidateQueries({ queryKey: ["workspace-task"] });
    qc.invalidateQueries({ queryKey: ["workspace-history"] });
  };
  useEffect(() => {
    if (focused.data) {
      setOwner(focused.data.assignee_id || "");
      setMeasures(focused.data.measures);
      setCost(focused.data.actual_cost_cny);
      setResult("");
    }
  }, [focused.data]);
  async function transition(action: string) {
    const t = focused.data;
    if (!t) return;
    const body: {
      id: string;
      expected_version: number;
      action: string;
      assignee_id?: string | null;
      measures?: string;
      result?: string;
      actual_cost_cny?: string;
    } = { id: t.id, expected_version: t.version, action };
    if (action === "assign") body.assignee_id = owner || null;
    if (action === "start") body.measures = measures;
    if (["submit", "complete", "reopen", "cancel"].includes(action))
      body.result = result;
    if (action === "submit") body.actual_cost_cny = cost;
    const r = await change.mutateAsync(body).catch(() => null);
    if (r) {
      refresh();
      setNotice(
        "任务状态已保存；这记录人工处置，不代表系统已执行真实采购或通知。",
      );
    }
  }
  const t = focused.data;
  return (
    <div className="space-y-5" data-testid="actions-page">
      <div className="flex flex-wrap justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">处置与复盘</h1>
          <p className="mt-2 text-sm text-slate-500">
            从风险事件或方案建立任务，落实责任、费用与验证结果。
          </p>
        </div>
        <Link href="/workspace" className="text-sm text-indigo-600">
          查看企业数据与报告 →
        </Link>
      </div>
      <div className="grid gap-3 sm:grid-cols-5">
        {Object.entries(states).map(([id, label]) => (
          <button
            key={id}
            onClick={() => {
              setFilter(filter === id ? "" : id);
              setOffset(0);
            }}
            aria-pressed={filter === id}
            className={`rounded-xl border p-4 text-left text-sm ${filter === id ? "border-indigo-300 bg-indigo-50 text-indigo-700" : "bg-white text-slate-500"}`}
          >
            {label}
          </button>
        ))}
      </div>
      {notice && (
        <p
          role="status"
          className="rounded-xl bg-teal-50 p-3 text-sm text-teal-800"
        >
          {notice}
        </p>
      )}
      {[create, change, archive]
        .filter((x) => x.isError)
        .map((x, i) => (
          <p
            key={i}
            role="alert"
            className="rounded-xl bg-red-50 p-3 text-sm text-red-700"
          >
            {workspaceError(x.error)}{" "}
            <button
              onClick={() => {
                refresh();
                change.reset();
              }}
              className="underline"
            >
              重新加载核对
            </button>
          </p>
        ))}
      {requestedEvent && !recordId && (
        <section className={card}>
          <h2 className="font-semibold">将模拟事件转为企业处置记录</h2>
          <p className="mt-2 text-xs text-slate-500">
            事件 {requestedEvent}
            ，来源为演示场景。主动保存后，本企业两类角色均可协作；不会自动成为真实风险预测。
          </p>
          <button
            className={button + " mt-4"}
            disabled={archive.isPending}
            onClick={async () => {
              const r = await archive.mutateAsync(scenario).catch(() => null);
              if (r) {
                const e = r.events.find((e) => e.code === requestedEvent);
                setRecordId(e?.id || r.events[0]?.id || "");
                setTitle(e ? "处置：" + e.name : "风险跟进");
                qc.invalidateQueries({
                  queryKey: ["workspace-source-options"],
                });
                setNotice("演示场景已持久化，来源明确标注为模拟。");
              }
            }}
          >
            保存模拟事件，准备建任务
          </button>
        </section>
      )}
      <div className="grid gap-5 xl:grid-cols-[1fr_1.1fr]">
        <section className={card}>
          <h2 className="font-semibold">新建处置任务</h2>
          <div className="mt-4 space-y-3">
            <label className="block text-xs text-slate-500">
              业务依据
              <input
                aria-label="搜索业务依据"
                placeholder="输入编号或名称筛选依据"
                value={sourceQuery}
                onChange={(e) => setSourceQuery(e.target.value)}
                className={field}
              />
              <select
                aria-label="业务依据"
                value={recordId}
                onChange={(e) => setRecordId(e.target.value)}
                className={field}
              >
                <option value="">选择本企业记录</option>
                {requestedSource.data &&
                  !records.data?.items.some(
                    (r) => r.id === requestedSource.data.id,
                  ) && (
                    <option value={requestedSource.data.id}>
                      {requestedSource.data.code} · {requestedSource.data.name}
                    </option>
                  )}
                {records.data?.items.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.code} · {r.name} · {sources[r.source_type]}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs text-slate-500">
              任务名称
              <input
                aria-label="任务名称"
                value={title}
                maxLength={160}
                onChange={(e) => setTitle(e.target.value)}
                className={field}
              />
            </label>
            <label className="block text-xs text-slate-500">
              截止时间
              <input
                aria-label="截止时间"
                type="datetime-local"
                value={due}
                onChange={(e) => setDue(e.target.value)}
                className={field}
              />
            </label>
            <label className="block text-xs text-slate-500">
              责任人
              <select
                aria-label="新任务责任人"
                value={draftOwner}
                onChange={(e) => setDraftOwner(e.target.value)}
                className={field}
              >
                <option value="">暂不分配</option>
                {members.data?.items.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} · {m.email}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-xs text-slate-500">
              处置措施
              <textarea
                aria-label="新任务措施"
                value={draftMeasures}
                maxLength={2000}
                onChange={(e) => setDraftMeasures(e.target.value)}
                className={field}
              />
            </label>
            <button
              disabled={!recordId || !title.trim() || !due || create.isPending}
              className={button}
              onClick={async () => {
                const r = await create
                  .mutateAsync({
                    record_id: recordId,
                    title,
                    due_at: new Date(due).toISOString(),
                    assignee_id: draftOwner || null,
                    measures: draftMeasures,
                  })
                  .catch(() => null);
                if (r) {
                  setSelected(r.id);
                  setTitle("");
                  setFilter("");
                  refresh();
                  setNotice("处置任务已保存，可在本企业协作和回放状态变更。");
                }
              }}
            >
              创建处置任务
            </button>
          </div>
          <p className="mt-4 text-xs leading-5 text-slate-400">
            缺少业务依据时，可在企业数据工作区导入记录，或从风险研判、模拟结果主动归档。这里只记录人工处置，不发送外部消息或执行真实业务。
          </p>
        </section>
        <section className={card}>
          <h2 className="font-semibold">任务清单</h2>
          {tasks.isError && (
            <p role="alert" className="mt-3 text-red-600">
              读取失败，请重试。
            </p>
          )}
          <div className="mt-4 space-y-3">
            {tasks.data?.items.map((task) => (
              <button
                key={task.id}
                onClick={() => {
                  setSelected(task.id);
                  change.reset();
                }}
                className={`w-full rounded-xl border p-4 text-left ${selected === task.id ? "border-indigo-300 bg-indigo-50" : ""}`}
              >
                <div className="flex justify-between gap-2 text-sm">
                  <span className="font-medium">{task.title}</span>
                  <span className="shrink-0 text-xs text-slate-500">
                    {states[task.state]}
                  </span>
                </div>
                <p className="mt-2 text-xs text-slate-400">
                  截止 {new Date(task.due_at).toLocaleString("zh-CN")} · 版本
                  {task.version}
                </p>
              </button>
            ))}
            {tasks.data?.total === 0 && (
              <p className="py-10 text-sm text-slate-400">
                暂无任务。先选择业务依据创建第一项处置。
              </p>
            )}
          </div>
          <p className="mt-4 text-xs text-slate-400">
            共 {tasks.data?.total || 0} 项；当前每页20项，可按状态筛选。
          </p>
          <div className="mt-3 flex gap-4 text-xs">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - 20))}
            >
              上一页任务
            </button>
            <button
              disabled={offset + 20 >= (tasks.data?.total || 0)}
              onClick={() => setOffset(offset + 20)}
            >
              下一页任务
            </button>
          </div>
        </section>
      </div>
      {t && (
        <section className={card} data-testid="task-detail">
          <div className="flex flex-wrap justify-between gap-3">
            <h2 className="font-semibold">
              {t.title} · {states[t.state]}
            </h2>
            <span className="text-xs text-slate-400">版本 {t.version}</span>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            依据 {source.data?.code} · {sources[source.data?.source_type || ""]}{" "}
            · 人工填报费用 ¥{t.actual_cost_cny}
          </p>
          <p className="mt-2 text-xs text-slate-500">
            已保存结果：{t.result || "尚未填写"}
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <label className="text-xs text-slate-500">
              任务责任人
              <select
                aria-label="任务责任人"
                disabled={
                  ["completed", "cancelled"].includes(t.state) ||
                  change.isPending
                }
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                className={field}
              >
                <option value="">未分配</option>
                {members.data?.items.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-xs text-slate-500">
              人工填报执行费用（元）
              <input
                aria-label="执行费用"
                disabled={
                  ["completed", "cancelled"].includes(t.state) ||
                  change.isPending
                }
                type="number"
                min="0"
                step="0.01"
                value={cost}
                onChange={(e) => setCost(e.target.value)}
                className={field}
              />
            </label>
            <label className="text-xs text-slate-500">
              执行措施
              <textarea
                aria-label="执行措施"
                disabled={
                  ["completed", "cancelled"].includes(t.state) ||
                  change.isPending
                }
                value={measures}
                onChange={(e) => setMeasures(e.target.value)}
                maxLength={2000}
                className={field}
              />
            </label>
          </div>
          <label className="mt-4 block text-xs text-slate-500">
            结果、验证依据或取消/退回原因
            <textarea
              aria-label="结果与验证说明"
              disabled={
                ["completed", "cancelled"].includes(t.state) || change.isPending
              }
              value={
                ["completed", "cancelled"].includes(t.state) ? t.result : result
              }
              maxLength={2000}
              onChange={(e) => setResult(e.target.value)}
              className={field}
            />
          </label>
          <div className="mt-4 flex flex-wrap gap-2">
            {!["completed", "cancelled"].includes(t.state) && (
              <button
                className="rounded-lg border px-4 py-2 text-sm"
                disabled={change.isPending}
                onClick={() => transition("assign")}
              >
                保存责任人
              </button>
            )}
            {t.state === "open" && (
              <button
                className={button}
                disabled={change.isPending}
                onClick={() => transition("start")}
              >
                开始处理
              </button>
            )}
            {t.state === "in_progress" && (
              <button
                className={button}
                disabled={change.isPending || !result.trim()}
                onClick={() => transition("submit")}
              >
                提交验证
              </button>
            )}
            {t.state === "pending_verification" && (
              <>
                <button
                  className={button}
                  disabled={change.isPending || !result.trim()}
                  onClick={() => transition("complete")}
                >
                  验证通过并完成
                </button>
                <button
                  className="rounded-lg border px-4 py-2 text-sm"
                  disabled={change.isPending || !result.trim()}
                  onClick={() => transition("reopen")}
                >
                  退回处理
                </button>
              </>
            )}
            {!["completed", "cancelled"].includes(t.state) && (
              <button
                className="rounded-lg border px-4 py-2 text-sm text-red-600"
                disabled={change.isPending || !result.trim()}
                onClick={() => transition("cancel")}
              >
                取消任务
              </button>
            )}
          </div>
          <h3 className="mt-6 text-sm font-medium">状态变更与复盘依据</h3>
          <div className="mt-3 space-y-2">
            {history.data?.items.map((h) => (
              <details
                key={h.id}
                className="rounded-lg bg-slate-50 p-3 text-xs"
              >
                <summary className="cursor-pointer">
                  {h.action === "task.created" ? "创建任务" : "更新任务"} ·{" "}
                  {new Date(h.created_at).toLocaleString("zh-CN")}
                </summary>
                <pre className="mt-3 overflow-auto whitespace-pre-wrap break-all text-slate-500">
                  {JSON.stringify(h.detail, null, 2)}
                </pre>
              </details>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
