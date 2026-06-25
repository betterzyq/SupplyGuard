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
        title="Secure RAG Workbench"
        description="Role-filtered retrieval — not ordinary RAG. See Qdrant filters, chunks and citations."
      />
      <div className="grid gap-6 lg:grid-cols-3">
        <SectionCard title="Query">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            rows={4}
            className="w-full rounded-lg border border-slate-300 p-3 text-sm"
          />
          <label className="mt-3 block text-xs text-slate-500">top_k: {topK}</label>
          <input type="range" min={1} max={20} value={topK} onChange={(e) => setTopK(+e.target.value)} className="w-full" />
          <button
            type="button"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="mt-4 w-full rounded-lg bg-brand-600 py-2 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
          >
            {mutation.isPending ? "Querying…" : "Run Secure RAG"}
          </button>
          <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs">
            <p className="font-medium text-slate-600 mb-2">Pipeline</p>
            <p>User Role → Permission Context → Qdrant Filter → Vector Search → LLM → Review</p>
          </div>
        </SectionCard>

        <div className="lg:col-span-2 space-y-4">
          <SectionCard title="Answer">
            {result ? (
              <>
                <div className="flex gap-2 mb-3">
                  <PermissionDecisionBadge decision={result.status === "blocked" ? "denied" : "allowed"} />
                  <Link href={`/traces?trace=${result.trace_id}`}><TraceIdBadge traceId={result.trace_id} /></Link>
                </div>
                <pre className="whitespace-pre-wrap text-sm text-slate-800">{result.answer}</pre>
              </>
            ) : (
              <p className="text-sm text-slate-400">Run a query to see results</p>
            )}
          </SectionCard>
          {result && (
            <>
              <SectionCard title="Qdrant Filter Applied">
                <pre className="text-xs overflow-auto bg-slate-50 p-3 rounded-lg">{JSON.stringify(result.retrieval.filter_applied, null, 2)}</pre>
              </SectionCard>
              <SectionCard title={`Citations (${result.citations.length})`}>
                <div className="space-y-2">
                  {result.citations.map((c, i) => (
                    <div key={i} className="rounded-lg border border-slate-100 p-3 text-sm">
                      <p className="font-medium">{c.title}</p>
                      <p className="text-xs text-slate-500">chunk {c.chunk_index} · score {c.score.toFixed(3)}</p>
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
