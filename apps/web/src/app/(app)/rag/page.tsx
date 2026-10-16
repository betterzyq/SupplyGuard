"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";
import { TraceIdBadge } from "@/components/badges/TraceIdBadge";
import { ragQuery } from "@/lib/api";
import Link from "next/link";

export default function RagPage() {
  const [query, setQuery] = useState("供应商 SUP-001 的合同付款条款是什么？");
  const [topK, setTopK] = useState(5);

  const mutation = useMutation({
    mutationFn: () => ragQuery({ query, top_k: topK }),
  });

  const result = mutation.data;

  return (
    <div>
      <PageHeader
        title="Secure RAG 工作台"
        description="按角色权限检索证据，查看 Qdrant 过滤条件、文档分块与引用来源。"
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard title="问题查询">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-slate-300 p-3 text-sm"
          />
          <label className="mt-3 block text-xs text-slate-500">检索数量（Top K）：{topK}</label>
          <input type="range" min={1} max={20} value={topK} onChange={(e) => setTopK(+e.target.value)} className="w-full" />
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="mt-4 w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {mutation.isPending ? "查询中…" : "运行 Secure RAG"}
          </button>
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs">
            <p className="font-medium text-slate-600 mb-2">处理流程</p>
            <p>用户角色 → 权限上下文 → Qdrant 过滤 → 向量检索 → LLM → 审核</p>
          </div>
        </SectionCard>

        <div className="lg:col-span-2 space-y-4">
          <SectionCard title="回答">
            {result ? (
              <>
                <div className="flex gap-2 mb-3">
                  <PermissionDecisionBadge decision={result.status === "blocked" ? "denied" : "allowed"} />
                  <Link href={`/traces?trace=${result.trace_id}`}><TraceIdBadge traceId={result.trace_id} /></Link>
                </div>
                <pre className="whitespace-pre-wrap text-sm text-slate-800">{result.answer}</pre>
              </>
            ) : (
              <p className="text-sm text-slate-400">提交问题后查看回答</p>
            )}
          </SectionCard>
          {result && (
            <>
              <SectionCard title="已应用的 Qdrant 过滤条件">
                <pre className="text-xs overflow-auto bg-slate-50 p-3 rounded-lg">{JSON.stringify(result.retrieval.filter_applied, null, 2)}</pre>
              </SectionCard>
              <SectionCard title={`引用来源（${result.citations.length}）`}>
                <div className="space-y-2">
                  {result.citations.map((c, i) => (
                    <div key={i} className="rounded-lg border border-slate-100 p-3 text-sm">
                      <p className="font-medium">{c.title}</p>
                      <p className="text-xs text-slate-500">分块 {c.chunk_index} · 相似度 {c.score.toFixed(3)}</p>
                      <p className="mt-1 text-xs text-slate-600">{c.snippet}</p>
                    </div>
                  ))}
                </div>
              </SectionCard>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
