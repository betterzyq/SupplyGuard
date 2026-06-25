"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { listLongTermMemory } from "@/lib/api";

export default function MemoryPage() {
  const { data } = useQuery({ queryKey: ["memory-lt"], queryFn: listLongTermMemory });

  return (
    <div>
      <PageHeader title="Memory" description="Session and long-term memory with permission-safe context rules." />
      <SectionCard title="Safety Rules">
        <ul className="text-sm text-slate-600 space-y-1 list-disc pl-5">
          <li>Never store API keys or full contract text</li>
          <li>external_supplier scoped by supplier_id</li>
          <li>Memory supplements but does not override RAG/GraphRAG facts</li>
        </ul>
      </SectionCard>
      <SectionCard title="Long-term Memory" className="mt-6">
        <div className="space-y-3">
          {((data as { items?: { id: string; memory_type: string; content: string; summary?: string }[] })?.items || []).map((m) => (
            <div key={m.id} className="rounded-lg border p-3 text-sm">
              <span className="text-xs text-brand-600">{m.memory_type}</span>
              <p className="mt-1">{m.content}</p>
            </div>
          ))}
          {!data && <p className="text-sm text-slate-400">No memory records</p>}
        </div>
      </SectionCard>
    </div>
  );
}
