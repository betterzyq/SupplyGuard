"use client";

import { displayLabel, errorLabel, graphPathLabel } from "@/lib/labels";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { SupplyChainGraph } from "@/components/supply-chain/SupplyChainGraph";
import { TraceIdBadge } from "@/components/badges/TraceIdBadge";
import { graphragQuery } from "@/lib/api";
import { formatLatency } from "@/lib/utils";

const QUERY_TYPES = [
  "supplier_impact",
  "product_dependency",
  "supplier_alternatives",
  "delivery_delay_impact",
  "quality_issue_trace",
  "customer_order_dependency",
];

const QUERY_HINTS: Record<string, string> = {
  supplier_impact: "实体编码填写供应商编码：演示数据如 SUP-001；SCMS 真实数据如 SCMS-ranbaxy-fine-chemicals-ltd",
  product_dependency: "实体编码填写产品编码，如 P001 或 DC-957",
  supplier_alternatives: "实体编码填写供应商编码",
  delivery_delay_impact: "实体编码填写供应商编码（SUP-001）或订单编码（DC-1）",
  quality_issue_trace: "实体编码可选，填写质量问题 ID",
  customer_order_dependency: "实体编码填写客户编码",
};

export default function GraphRagPage() {
  const [query, setQuery] = useState("供应商 SUP-001 延迟会影响哪些产品、订单和客户？");
  const [queryType, setQueryType] = useState("supplier_impact");
  const [entityCode, setEntityCode] = useState("SUP-001");

  const mutation = useMutation({
    mutationFn: () => graphragQuery({ query, query_type: queryType, entity_code: entityCode, top_k: 20 }),
  });

  const result = mutation.data;

  return (
    <div>
      <PageHeader title="GraphRAG 分析" description="通过 Cypher 模板探索供应链多跳路径。" />
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard title="GraphRAG 查询">
          <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={3} className="w-full rounded-lg border p-2 text-sm" />
          <select value={queryType} onChange={(e) => setQueryType(e.target.value)} className="mt-3 w-full rounded-lg border p-2 text-sm">
            {QUERY_TYPES.map((t) => (
              <option key={t} value={t}>{displayLabel(t)}</option>
            ))}
          </select>
          <p className="mt-2 text-xs text-slate-500">{QUERY_HINTS[queryType]}</p>
          <input value={entityCode} onChange={(e) => setEntityCode(e.target.value)} placeholder="实体编码" className="mt-2 w-full rounded-lg border p-2 text-sm" />
          <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending} className="mt-4 w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            {mutation.isPending ? "查询中…" : "运行 GraphRAG"}
          </button>
        </SectionCard>
        <div className="lg:col-span-2 space-y-4 min-h-[520px]">
          {mutation.isPending && (
            <div className="flex h-[520px] items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-sm text-slate-500">
              正在查询图谱…
            </div>
          )}
          {mutation.isError && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              查询失败：{errorLabel((mutation.error as Error)?.message, "未知错误")}
            </div>
          )}
          {result && !mutation.isPending && (
            <>
              <div className="flex flex-wrap gap-2 text-sm">
                <Link href={`/traces?trace=${result.trace_id}`}><TraceIdBadge traceId={result.trace_id} /></Link>
                <span className="text-slate-500">{formatLatency(result.latency_ms)} · {displayLabel(result.cypher_template)}</span>
                <span className="text-slate-500">· {result.result_count} 条路径</span>
              </div>
              {result.result_count === 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  <p className="font-medium">未找到匹配的图谱路径</p>
                  <p className="mt-1 text-amber-800">
                    {queryType === "delivery_delay_impact"
                      ? "delivery_delay_impact 支持供应商编码（如 SUP-001）或订单编码（如 DC-1）。若使用 DC-* 订单，请确认已执行 make build-real-graph。"
                      : queryType === "supplier_impact" && entityCode.startsWith("SCMS-")
                        ? "SCMS 真实供应商需先执行 make build-real-graph -- --reset-graph --limit 5000 建图后再查。"
                        : "请检查实体编码是否与 Neo4j 节点编码一致（演示数据：SUP-001；真实数据：SCMS-* / DC-*），或尝试其他查询类型。"}
                  </p>
                </div>
              )}
              <div className="h-[520px]">
                <SupplyChainGraph
                  variant="propagation"
                  title="供应链影响扩散分析"
                  graphPaths={result.graph_paths as unknown as Record<string, unknown>[]}
                  affected={{
                    suppliers: result.affected_suppliers,
                    materials: result.affected_materials,
                    products: result.affected_products,
                    orders: result.affected_orders,
                    customers: result.affected_customers,
                  }}
                  sourceCode={entityCode}
                />
              </div>
              <SectionCard title="路径说明">
                {result.graph_paths.length === 0 ? (
                  <p className="text-sm text-slate-500">无路径说明</p>
                ) : (
                  result.graph_paths.map((p) => (
                    <div key={p.path_index} className="mb-4 border-b pb-4 last:border-0">
                      <p className="text-xs text-brand-600 font-mono mb-1">{p.graph_path_ref}</p>
                      <p className="text-sm text-slate-800">{graphPathLabel(p.path_text)}</p>
                    </div>
                  ))
                )}
              </SectionCard>
            </>
          )}
          {!mutation.isPending && !result && !mutation.isError && (
            <div className="flex h-[520px] items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-400">
              填写查询参数后点击“运行 GraphRAG”
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
