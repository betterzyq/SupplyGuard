"use client";

import { displayLabel, actionLabel, graphPathLabel } from "@/lib/labels";
import { useState } from "react";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { Loader2, Zap } from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { SupplyChainGraph } from "@/components/supply-chain/SupplyChainGraph";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";
import { TraceIdBadge } from "@/components/badges/TraceIdBadge";
import { runImpactSimulation } from "@/lib/api";
import { formatLatency } from "@/lib/utils";

export default function SupplyChainPage() {
  const [sourceType, setSourceType] = useState("supplier");
  const [sourceCode, setSourceCode] = useState("SUP-001");
  const [riskType, setRiskType] = useState("delivery_delay");
  const [severity, setSeverity] = useState("critical");

  const simulation = useMutation({
    mutationFn: () =>
      runImpactSimulation({
        source_node_type: sourceType,
        source_node_code: sourceCode,
        risk_type: riskType,
        severity,
        include_alternatives: true,
        include_actions: true,
      }),
  });

  const result = simulation.data;

  return (
    <div className="flex h-[calc(100vh-7rem)] flex-col">
      <PageHeader
        title="供应链图谱"
        description="可视化查看风险在供应商、物料、产品、订单和客户之间的传播路径。"
      />

      <div className="flex flex-1 gap-4 min-h-0">
        {/* Left control panel */}
        <div className="w-72 shrink-0 space-y-4 overflow-y-auto">
          <SectionCard title="风险模拟" description="设置风险源与影响条件">
            <div className="space-y-3 text-sm">
              <div>
                <label className="text-xs font-medium text-slate-500">风险源节点类型</label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                >
                  <option value="supplier">供应商</option>
                  <option value="material">物料</option>
                  <option value="product">产品</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500">实体编码</label>
                <select
                  value={sourceCode}
                  onChange={(e) => setSourceCode(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                >
                  <option value="SUP-001">SUP-001 (Alpha Components)</option>
                  <option value="SUP-002">SUP-002 (Beta Materials)</option>
                  <option value="SUP-003">SUP-003</option>
                  <option value="M001">M001</option>
                  <option value="P001">P001</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500">风险类型</label>
                <select
                  value={riskType}
                  onChange={(e) => setRiskType(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                >
                  <option value="delivery_delay">交付延误</option>
                  <option value="quality_failure">质量异常</option>
                  <option value="financial_risk">财务风险</option>
                  <option value="compliance_risk">合规风险</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500">严重程度</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value)}
                  className="mt-1 w-full rounded-lg border border-slate-300 px-2 py-1.5"
                >
                  <option value="low">低</option>
                  <option value="medium">中</option>
                  <option value="high">高</option>
                  <option value="critical">严重</option>
                </select>
              </div>
              <button
                type="button"
                onClick={() => simulation.mutate()}
                disabled={simulation.isPending}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-600 py-2 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
              >
                {simulation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
                运行影响模拟
              </button>
            </div>
          </SectionCard>
        </div>

        {/* Center graph */}
        <div className="flex-1 min-w-0 flex flex-col gap-4">
          <div className="flex-1 min-h-[300px]">
            <SupplyChainGraph
              graphPaths={result?.graph_paths || []}
              affected={{
                suppliers: result?.affected_suppliers,
                materials: result?.affected_materials,
                products: result?.affected_products,
                orders: result?.affected_orders,
                customers: result?.affected_customers,
              }}
              sourceCode={sourceCode}
              className="h-full"
            />
          </div>

          {/* Agent actions */}
          {result?.agent_actions && (
            <SectionCard title="Agent 建议措施">
              <div className="grid gap-2 sm:grid-cols-2">
                {(result.agent_actions as { action: string; agent: string; permission: string; status: string }[]).map(
                  (a, i) => (
                    <div key={i} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
                      <p className="font-medium text-slate-800">{actionLabel(a.action)}</p>
                      <p className="text-xs text-slate-500 mt-1">
                        {displayLabel(a.agent)} · {displayLabel(a.permission)} · {displayLabel(a.status)}
                      </p>
                    </div>
                  )
                )}
              </div>
            </SectionCard>
          )}
        </div>

        {/* Right impact panel */}
        <div className="w-80 shrink-0 space-y-4 overflow-y-auto">
          <SectionCard title="影响分析">
            {!result ? (
              <p className="text-sm text-slate-400">运行模拟后查看影响分析</p>
            ) : (
              <div className="space-y-4 text-sm">
                <div>
                  <p className="text-xs text-slate-500">风险源</p>
                  <p className="font-medium">
                    {displayLabel((result.risk_source as { node_type: string; node_code: string }).node_type)}{" "}
                    {(result.risk_source as { node_code: string }).node_code}
                  </p>
                </div>
                <div className="flex gap-2">
                  <PermissionDecisionBadge decision={result.permission_decision as string} />
                  {result.trace_id && (
                    <Link href={`/traces?trace=${result.trace_id}`}>
                      <TraceIdBadge traceId={result.trace_id as string} />
                    </Link>
                  )}
                </div>
                <p className="text-xs text-slate-500">响应耗时：{formatLatency(result.latency_ms as number)}</p>
                {[
                  ["受影响物料", result.affected_materials],
                  ["受影响产品", result.affected_products],
                  ["受影响订单", result.affected_orders],
                  ["受影响客户", result.affected_customers],
                  ["替代供应商", result.alternative_suppliers],
                ].map(([label, items]) => (
                  <div key={label as string}>
                    <p className="text-xs font-medium text-slate-500">{label as string}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {((items as string[]) || []).length ? (
                        (items as string[]).map((c) => (
                          <span key={c} className="rounded bg-orange-100 px-2 py-0.5 text-xs text-orange-800">
                            {c}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-slate-400">—</span>
                      )}
                    </div>
                  </div>
                ))}
                <div>
                  <p className="text-xs font-medium text-slate-500 mb-2">影响路径</p>
                  {((result.impacted_paths as { path_text: string; hop_count: number }[]) || []).map((p, i) => (
                    <div key={i} className="mb-2 rounded bg-slate-50 p-2 text-xs">
                      <p className="text-slate-700">{graphPathLabel(p.path_text)}</p>
                      <p className="text-slate-400 mt-0.5">{p.hop_count} 跳</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </SectionCard>
        </div>
      </div>
    </div>
  );
}
