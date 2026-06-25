"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import ReactECharts from "echarts-for-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { StatCard } from "@/components/common/StatCard";
import { listBenchmarkRuns, runBenchmark } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/lib/utils";

const BENCHMARK_MODES = [
  { value: "secure_rag", label: "Secure RAG" },
  { value: "graphrag", label: "GraphRAG" },
  { value: "memory", label: "Memory" },
  { value: "permission", label: "Permission" },
  { value: "all", label: "All modes" },
] as const;

function num(v: unknown): number | null {
  return typeof v === "number" && !Number.isNaN(v) ? v : null;
}

function pct(v: number | null, digits = 0): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export default function BenchmarksPage() {
  const user = useAuthStore((s) => s.user);
  const isAdmin = user?.roles.includes("admin");
  const queryClient = useQueryClient();

  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const [runName, setRunName] = useState("web_benchmark");
  const [runMode, setRunMode] = useState<(typeof BENCHMARK_MODES)[number]["value"]>("secure_rag");
  const [runLimit, setRunLimit] = useState(10);

  const { data: runs, isError, error, isLoading } = useQuery({
    queryKey: ["benchmark-runs"],
    queryFn: () => listBenchmarkRuns(20),
    enabled: isAdmin,
    refetchInterval: (query) => {
      const items = query.state.data;
      const hasRunning =
        pendingRunId != null || items?.some((r) => r.status === "running" || r.status === "queued");
      return hasRunning ? 3000 : false;
    },
  });

  useEffect(() => {
    if (!pendingRunId || !runs?.length) return;
    const pending = runs.find((r) => r.id === pendingRunId);
    if (pending && (pending.status === "completed" || pending.status === "failed")) {
      setPendingRunId(null);
      setSelectedRunId(pendingRunId);
    }
  }, [runs, pendingRunId]);

  useEffect(() => {
    if (!runs?.length) return;
    if (!selectedRunId || !runs.some((r) => r.id === selectedRunId)) {
      setSelectedRunId(runs[0].id);
    }
  }, [runs, selectedRunId]);

  const selectedRun = useMemo(
    () => runs?.find((r) => r.id === selectedRunId) ?? runs?.[0],
    [runs, selectedRunId]
  );

  const summary = selectedRun?.summary as Record<string, unknown> | undefined;
  const recall = num(summary?.recall_at_k);
  const citation = num(summary?.citation_accuracy);
  const graphHit = num(summary?.graph_path_hit_rate);
  const memoryHit = num(summary?.memory_hit_rate);
  const blocked = num(summary?.blocked_accuracy);
  const permViolation = num(summary?.permission_violation_rate);
  const p95 = num(summary?.p95_latency_ms);

  const runMutation = useMutation({
    mutationFn: () =>
      runBenchmark({
        name: runName.trim() || "web_benchmark",
        mode: runMode,
        limit: runLimit,
        config: { permission_filter: true, top_k: 5 },
      }),
    onSuccess: async (res) => {
      await queryClient.invalidateQueries({ queryKey: ["benchmark-runs"] });
      if (res.benchmark_run_id) {
        setSelectedRunId(res.benchmark_run_id);
        if (res.status === "running") {
          setPendingRunId(res.benchmark_run_id);
        } else {
          setPendingRunId(null);
        }
      }
    },
  });

  const isJobRunning =
    pendingRunId != null || runs?.some((r) => r.status === "running" || r.status === "queued");

  const radarOption = summary
    ? {
        tooltip: {},
        radar: {
          indicator: [
            { name: "Recall@K", max: 1 },
            { name: "Citation", max: 1 },
            { name: "Graph Hit", max: 1 },
            { name: "Memory Hit", max: 1 },
            { name: "Blocked Acc", max: 1 },
          ],
        },
        series: [
          {
            type: "radar",
            data: [
              {
                value: [
                  recall ?? 0,
                  citation ?? 0,
                  graphHit ?? 0,
                  memoryHit ?? 0,
                  blocked ?? 0,
                ],
                name: selectedRun?.name || selectedRun?.mode || "Benchmark",
                areaStyle: { opacity: 0.15 },
              },
            ],
          },
        ],
      }
    : null;

  if (!isAdmin) {
    return (
      <div>
        <PageHeader title="Benchmarks" description="Admin only — deterministic evaluation dashboard." />
        <p className="text-sm text-red-600">Benchmark API requires admin role. Log in as admin@example.com.</p>
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="Benchmark Experiments"
        description="Prove Secure RAG, GraphRAG, Memory and permission controls."
      />

      <SectionCard title="Run Benchmark" className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label className="block text-sm">
            <span className="text-slate-600">Name</span>
            <input
              value={runName}
              onChange={(e) => setRunName(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              placeholder="web_benchmark"
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">Mode</span>
            <select
              value={runMode}
              onChange={(e) => setRunMode(e.target.value as typeof runMode)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {BENCHMARK_MODES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">Limit (questions)</span>
            <input
              type="number"
              min={1}
              max={500}
              value={runLimit}
              onChange={(e) => setRunLimit(Number(e.target.value) || 10)}
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
          </label>
          <div className="flex items-end">
            <button
              type="button"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending || isJobRunning}
              className="w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              {runMutation.isPending ? "提交中…" : isJobRunning ? "运行中…" : "Run Benchmark"}
            </button>
          </div>
        </div>
        {(runMutation.isPending || isJobRunning) && (
          <p className="mt-3 text-sm text-amber-700 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
            Benchmark 已在后台运行，页面将每 3 秒自动刷新状态。100 题约需 5–10 分钟，请勿关闭页面。
          </p>
        )}
        {runMutation.isError && (
          <p className="mt-3 text-sm text-red-600 rounded-lg border border-red-200 bg-red-50 px-3 py-2">
            提交失败：{(runMutation.error as Error)?.message || "未知错误"}
          </p>
        )}
        {runMutation.isSuccess && runMutation.data.status === "running" && (
          <p className="mt-3 text-sm text-blue-700 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2">
            任务已提交（run id: {runMutation.data.benchmark_run_id?.slice(0, 8)}…），等待后台完成…
          </p>
        )}
        {runMutation.isSuccess && runMutation.data.status === "completed" && (
          <p className="mt-3 text-sm text-green-700 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
            运行完成。
          </p>
        )}
      </SectionCard>

      {isError && (
        <p className="mb-4 text-sm text-red-600 rounded-lg border border-red-200 bg-red-50 px-3 py-2">
          无法加载 Benchmark 数据：{(error as Error)?.message || "请确认已用 admin 登录且 API 已启动"}
        </p>
      )}

      {!isLoading && !isError && (!runs || runs.length === 0) && !isJobRunning && (
        <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">尚无 Benchmark 运行记录</p>
          <p className="mt-1 text-amber-800">使用上方表单运行第一次 Benchmark，或在项目根目录执行 CLI：</p>
          <pre className="mt-2 overflow-x-auto rounded bg-white/80 p-2 text-xs text-slate-800">
            {`make generate-eval\nmake bench`}
          </pre>
        </div>
      )}

      {selectedRun && (
        <p className="mb-3 text-sm text-slate-500">
          当前查看：<span className="font-medium text-slate-800">{selectedRun.name}</span>
          <span className="mx-2">·</span>
          {selectedRun.mode}
          <span className="mx-2">·</span>
          {selectedRun.status}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-4 mb-6">
        <StatCard title="Citation Accuracy" value={pct(citation)} />
        <StatCard
          title="Permission Violation"
          value={pct(permViolation, 1)}
          subtitle="Target: 0%"
        />
        <StatCard
          title="Graph Path Hit"
          value={pct(graphHit)}
          subtitle={graphHit == null && selectedRun ? "本模式无 Graph 指标" : undefined}
        />
        <StatCard
          title="P95 Latency"
          value={p95 != null ? `${Math.round(p95)}ms` : "—"}
        />
      </div>

      {radarOption && (
        <SectionCard title="Strategy Radar">
          <ReactECharts option={radarOption} style={{ height: 360 }} />
          {graphHit == null && (
            <p className="mt-2 text-xs text-slate-500">Graph Hit 轴在本 run 无有效数据（非 graphrag/all 模式时为 N/A）。</p>
          )}
        </SectionCard>
      )}

      <SectionCard title="Recent Runs" className="mt-6">
        <p className="mb-3 text-xs text-slate-500">点击一行以切换上方指标与雷达图</p>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-slate-500">
              <th className="pb-2 pr-4">Name</th>
              <th className="pb-2 pr-4">Mode</th>
              <th className="pb-2 pr-4">Status</th>
              <th className="pb-2">Started</th>
            </tr>
          </thead>
          <tbody>
            {(runs || []).map((r) => {
              const active = r.id === selectedRunId;
              return (
                <tr
                  key={r.id}
                  onClick={() => setSelectedRunId(r.id)}
                  className={cn(
                    "border-b border-slate-50 cursor-pointer transition-colors",
                    active ? "bg-brand-50 hover:bg-brand-50" : "hover:bg-slate-50"
                  )}
                >
                  <td className={cn("py-2 pr-4", active && "font-medium text-brand-700")}>{r.name}</td>
                  <td className="py-2 pr-4">{r.mode}</td>
                  <td className="py-2 pr-4">
                    <span
                      className={cn(
                        "inline-flex rounded-full px-2 py-0.5 text-xs",
                        r.status === "completed"
                          ? "bg-green-100 text-green-800"
                          : r.status === "failed"
                            ? "bg-red-100 text-red-800"
                            : "bg-amber-100 text-amber-800"
                      )}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="py-2 text-slate-500 text-xs">
                    {r.started_at ? new Date(r.started_at).toLocaleString() : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {isLoading && <p className="py-4 text-sm text-slate-500">加载中…</p>}
      </SectionCard>
    </div>
  );
}
