"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";
import { getTrace } from "@/lib/api";
import { formatLatency } from "@/lib/utils";

function TracesContent() {
  const searchParams = useSearchParams();
  const [traceId, setTraceId] = useState(searchParams.get("trace") || "");

  useEffect(() => {
    const t = searchParams.get("trace");
    if (t) setTraceId(t);
  }, [searchParams]);

  const { data, isFetching, refetch } = useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => getTrace(traceId),
    enabled: traceId.length > 8,
  });

  return (
    <div>
      <PageHeader title="Observability" description="Replay full agent execution by trace_id." />
      <div className="flex gap-2 mb-6">
        <input
          value={traceId}
          onChange={(e) => setTraceId(e.target.value)}
          placeholder="Enter trace_id"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm font-mono"
        />
        <button type="button" onClick={() => refetch()} className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white">
          Load
        </button>
      </div>
      {isFetching && <p className="text-sm text-slate-500">Loading…</p>}
      {data && (
        <div className="grid gap-6 lg:grid-cols-3">
          <SectionCard title="Summary">
            <div className="space-y-2 text-sm">
              <p>Latency: {formatLatency(data.summary.total_latency_ms as number)}</p>
              <p>Tokens: {String(data.summary.total_tokens)}</p>
              <p>Retrievals: {String(data.summary.retrieval_count)}</p>
              <p>Denied: {String(data.summary.permission_denied_count)}</p>
              <p>Errors: {String(data.summary.error_count)}</p>
              <p>Model: {String(data.summary.model || data.agent_run?.llm_model || "—")}</p>
            </div>
          </SectionCard>
          <div className="lg:col-span-2">
            <SectionCard title="Timeline">
              <div className="space-y-2">
                {data.timeline.map((ev, i) => (
                  <div key={i} className="flex items-center gap-3 rounded-lg border border-slate-100 p-3 text-sm">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs font-mono">{ev.type}</span>
                    <span className="font-medium">{ev.name}</span>
                    {ev.status && <PermissionDecisionBadge decision={ev.status === "denied" ? "denied" : "allowed"} />}
                    {ev.latency_ms != null && <span className="text-xs text-slate-400 ml-auto">{formatLatency(ev.latency_ms)}</span>}
                  </div>
                ))}
              </div>
            </SectionCard>
          </div>
          {data.tool_calls.length > 0 && (
            <SectionCard title="Tool Calls" className="lg:col-span-3">
              <pre className="text-xs overflow-auto">{JSON.stringify(data.tool_calls, null, 2)}</pre>
            </SectionCard>
          )}
        </div>
      )}
    </div>
  );
}

export default function TracesPage() {
  return (
    <Suspense fallback={<div>Loading…</div>}>
      <TracesContent />
    </Suspense>
  );
}
