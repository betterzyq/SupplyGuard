"use client";

import { toolLabel, toolDescription } from "@/lib/labels";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";
import { TraceIdBadge } from "@/components/badges/TraceIdBadge";
import { listTools, callTool } from "@/lib/api";

export default function ToolsPage() {
  const { data: registry } = useQuery({ queryKey: ["tools"], queryFn: listTools });
  const [selected, setSelected] = useState("query_supplier_profile");
  const [supplierCode, setSupplierCode] = useState("SUP-001");

  const mutation = useMutation({
    mutationFn: () =>
      callTool({
        tool_name: selected,
        tool_input: selected.includes("supplier") || selected.includes("delivery") ? { supplier_code: supplierCode } : {},
      }),
  });

  return (
    <div>
      <PageHeader title="MCP 工具" description="按角色控制工具访问权限，并记录调用审计日志。" />
      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="当前角色可用工具">
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {(registry?.tools || []).map((t) => (
              <button
                key={t.name}
                type="button"
                onClick={() => setSelected(t.name)}
                className={`w-full text-left rounded-lg border p-3 text-sm ${selected === t.name ? "border-brand-400 bg-brand-50" : "border-slate-100"}`}
              >
                <p className="font-medium">{toolLabel(t.name)}</p>
                <p className="text-xs font-mono text-slate-400">{t.name}</p>
                <p className="text-xs text-slate-500">{toolDescription(t.name, t.description)}</p>
                {t.high_risk && <span className="text-xs text-purple-600">高风险操作</span>}
              </button>
            ))}
          </div>
        </SectionCard>
        <SectionCard title="调用工具">
          <input value={supplierCode} onChange={(e) => setSupplierCode(e.target.value)} className="w-full rounded border p-2 text-sm mb-3" placeholder="供应商编码，例如 SUP-001" />
          <button type="button" onClick={() => mutation.mutate()} disabled={mutation.isPending} className="w-full rounded-lg bg-brand-600 py-2 text-sm text-white disabled:opacity-50">
            调用 {toolLabel(selected)}
          </button>
          {mutation.data && (
            <div className="mt-4 space-y-2">
              <PermissionDecisionBadge decision={mutation.data.status} />
              <Link href={`/traces?trace=${mutation.data.trace_id}`}><TraceIdBadge traceId={mutation.data.trace_id} /></Link>
              <pre className="text-xs bg-slate-50 p-3 rounded overflow-auto">{JSON.stringify(mutation.data.result, null, 2)}</pre>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
