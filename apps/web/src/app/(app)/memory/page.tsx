"use client";

import { displayLabel } from "@/lib/labels";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { listLongTermMemory } from "@/lib/api";

export default function MemoryPage() {
  const { data } = useQuery({ queryKey: ["memory-lt"], queryFn: listLongTermMemory });

  return (
    <div>
      <PageHeader title="记忆管理" description="管理会话记忆与长期记忆，遵循上下文访问权限规则。" />
      <SectionCard title="记忆使用规则">
        <ul className="text-sm text-slate-600 space-y-1 list-disc pl-5">
          <li>不存储 API Key 或完整合同正文</li>
          <li>外部供应商的记忆访问范围由 supplier_id 限定</li>
          <li>记忆用于补充上下文，不覆盖 RAG / GraphRAG 检索到的事实</li>
        </ul>
      </SectionCard>
      <SectionCard title="长期记忆" className="mt-6">
        <div className="space-y-3">
          {((data as { items?: { id: string; memory_type: string; content: string; summary?: string }[] })?.items || []).map((m) => (
            <div key={m.id} className="rounded-lg border p-3 text-sm">
              <span className="text-xs text-brand-600">{displayLabel(m.memory_type)}</span>
              <p className="mt-1">{m.content}</p>
            </div>
          ))}
          {!data && <p className="text-sm text-slate-400">暂无记忆记录</p>}
        </div>
      </SectionCard>
    </div>
  );
}
