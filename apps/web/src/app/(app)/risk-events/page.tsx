"use client";

import { displayLabel } from "@/lib/labels";
import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";

const EVENTS = [
  {
    id: "RE-001",
    title: "SUP-001 港口拥堵延误",
    event_type: "delivery_delay",
    severity: "high",
    supplier: "SUP-001",
    detected_at: "2024-06-15",
    status: "active",
    action: "评估替代供应商 SUP-004",
  },
  {
    id: "RE-002",
    title: "M002 尺寸公差异常",
    event_type: "quality_failure",
    severity: "medium",
    supplier: "SUP-001",
    detected_at: "2024-06-10",
    status: "investigating",
    action: "查看质量报告",
  },
  {
    id: "RE-003",
    title: "SUP-003 清关延误",
    event_type: "delivery_delay",
    severity: "medium",
    supplier: "SUP-003",
    detected_at: "2024-06-08",
    status: "monitoring",
    action: "查询交付状态",
  },
];

export default function RiskEventsPage() {
  return (
    <div>
      <PageHeader
        title="风险事件中心"
        description="从风险发现、影响分析到 Agent 响应，事件与演示图谱数据关联。"
      />
      <p className="mb-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        演示数据：事件卡片关联演示图谱中的交付事件、风险事件及 GraphRAG 分析入口。
      </p>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {EVENTS.map((ev) => (
          <SectionCard key={ev.id} title={ev.title}>
            <div className="space-y-2 text-sm">
              <p className="text-xs text-slate-500">{displayLabel(ev.event_type)} · {ev.detected_at}</p>
              <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${ev.severity === "high" ? "border-red-200 bg-red-100 text-red-800" : "border-yellow-200 bg-yellow-100 text-yellow-800"}`}>{displayLabel(ev.severity)}风险</span>
              <p>供应商：<strong>{ev.supplier}</strong></p>
              <p className="text-slate-600">{ev.action}</p>
              <div className="flex gap-2 pt-2">
                <Link href={`/supply-chain?source=${ev.supplier}`} className="text-xs text-brand-600 hover:underline">
                  查看影响图谱 →
                </Link>
                <Link href="/graphrag" className="text-xs text-brand-600 hover:underline">
                  GraphRAG →
                </Link>
              </div>
            </div>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}
