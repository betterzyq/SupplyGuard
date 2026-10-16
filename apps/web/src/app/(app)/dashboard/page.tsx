"use client";

import { displayLabel } from "@/lib/labels";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Play } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/common/StatCard";
import { SectionCard } from "@/components/common/SectionCard";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";
import { TraceIdBadge } from "@/components/badges/TraceIdBadge";
import { DEMO_SCENARIOS, getDashboardSummary, listAuditLogs } from "@/lib/api";
import { formatLatency } from "@/lib/utils";

const capabilities = [
  { key: "secure_rag", label: "Secure RAG", href: "/rag", desc: "按角色权限过滤的向量检索" },
  { key: "graphrag", label: "GraphRAG", href: "/graphrag", desc: "供应链多跳路径分析" },
  { key: "memory", label: "记忆管理", href: "/memory", desc: "会话记忆与长期上下文" },
  { key: "llm", label: "Agent 工作流", href: "/agent", desc: "基于 LangGraph 的工作流编排" },
  { key: "benchmark", label: "基准评测", href: "/benchmarks", desc: "确定性评测" },
  { key: "observability", label: "链路追踪", href: "/traces", desc: "完整执行链路回放" },
];

function capabilityBadgeClass(status?: string) {
  if (status === "ok") return "bg-green-100 text-green-700";
  if (status === "no_data") return "bg-amber-100 text-amber-700";
  if (status === "error") return "bg-red-100 text-red-700";
  return "bg-slate-100 text-slate-500";
}

export default function DashboardPage() {
  const { data: summary } = useQuery({ queryKey: ["dashboard"], queryFn: getDashboardSummary });
  const { data: audit } = useQuery({ queryKey: ["audit-recent"], queryFn: () => listAuditLogs(10) });

  const bench = summary?.benchmark_snapshot as Record<string, unknown> | null;

  return (
    <div>
      <PageHeader
        title="风险运营总览"
        description="集中查看供应链风险识别、影响追踪、证据检索与 AI Agent 协作情况，全程可审计。"
      />

      {/* Demo Scenarios */}
      <SectionCard title="演示场景" description="快速体验核心业务场景">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {DEMO_SCENARIOS.map((s) => (
            <Link
              key={s.id}
              href={s.path}
              className="group rounded-lg border border-slate-200 p-4 hover:border-brand-300 hover:bg-brand-50/50 transition-colors"
            >
              <div className="flex items-start justify-between">
                <Play className="h-4 w-4 text-brand-600 shrink-0 mt-0.5" />
                <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-brand-500" />
              </div>
              <p className="mt-2 text-sm font-medium text-slate-900">{s.title}</p>
              <p className="mt-1 text-xs text-slate-500 line-clamp-2">{s.query}</p>
            </Link>
          ))}
        </div>
      </SectionCard>

      {/* Capability Overview */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {capabilities.map((c) => (
          <Link
            key={c.label}
            href={c.href}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-card hover:border-brand-200 transition-colors"
          >
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-slate-900">{c.label}</h3>
              <span
                className={`text-xs px-2 py-0.5 rounded-full ${capabilityBadgeClass(summary?.capability_status?.[c.key])}`}
              >
                {displayLabel(summary?.capability_status?.[c.key])}
              </span>
            </div>
            <p className="mt-2 text-sm text-slate-500">{c.desc}</p>
          </Link>
        ))}
      </div>

      {/* Risk Operations Summary */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard title="权限拒绝次数" value={summary?.audit_stats?.denied_count ?? "—"} subtitle="来自审计日志" trend="up" />
        <StatCard title="引用准确率" value={bench?.citation_accuracy != null ? `${((bench.citation_accuracy as number) * 100).toFixed(0)}%` : "—"} subtitle="最近一次基准评测" />
        <StatCard title="图谱路径命中率" value={bench?.graph_path_hit_rate != null ? `${((bench.graph_path_hit_rate as number) * 100).toFixed(0)}%` : "—"} />
        <StatCard title="记忆命中率" value={bench?.memory_hit_rate != null ? `${((bench.memory_hit_rate as number) * 100).toFixed(0)}%` : "—"} />
        <StatCard title="P95 响应耗时" value={bench?.p95_latency_ms != null ? formatLatency(bench.p95_latency_ms as number) : "—"} />
      </div>

      {/* Supply Chain Preview */}
      <SectionCard title="供应链影响预览" description="查看 SUP-001 故障向下游传播的影响" className="mt-6">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {["SUP-001", "M001", "P001", "PO-2024-0001", "C001"].map((code, i) => (
            <span key={code} className="flex items-center gap-2">
              <span
                className={`rounded-lg px-3 py-1.5 font-medium ${
                  i === 0 ? "bg-red-100 text-red-800 ring-2 ring-red-400" : i <= 2 ? "bg-orange-100 text-orange-800" : "bg-yellow-100 text-yellow-800"
                }`}
              >
                {code}
              </span>
              {i < 4 && <span className="text-slate-400">→</span>}
            </span>
          ))}
        </div>
        <Link href="/supply-chain" className="mt-4 inline-flex items-center gap-1 text-sm text-brand-600 hover:underline">
          打开供应链图谱 <ArrowRight className="h-4 w-4" />
        </Link>
      </SectionCard>

      {/* Recent Audit */}
      <SectionCard title="最近权限事件" description="来自审计日志" className="mt-6">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="pb-2 pr-4">操作</th>
                <th className="pb-2 pr-4">权限判定</th>
                <th className="pb-2">原因</th>
              </tr>
            </thead>
            <tbody>
              {(audit?.items || []).slice(0, 8).map((item) => (
                <tr key={item.id} className="border-b border-slate-50">
                  <td className="py-2 pr-4 font-mono text-xs">{item.action}</td>
                  <td className="py-2 pr-4">
                    <PermissionDecisionBadge decision={item.permission_decision} />
                  </td>
                  <td className="py-2 text-slate-600 truncate max-w-xs">{item.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Link href="/audit" className="mt-3 inline-block text-sm text-brand-600 hover:underline">
          查看全部审计日志 →
        </Link>
      </SectionCard>
    </div>
  );
}
