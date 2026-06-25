"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";

const EVENTS = [
  {
    id: "RE-001",
    title: "SUP-001 Port Congestion Delay",
    event_type: "delivery_delay",
    severity: "high",
    supplier: "SUP-001",
    detected_at: "2024-06-15",
    status: "active",
    action: "Check alternative SUP-004",
  },
  {
    id: "RE-002",
    title: "M002 Dimensional Tolerance Issue",
    event_type: "quality_failure",
    severity: "medium",
    supplier: "SUP-001",
    detected_at: "2024-06-10",
    status: "investigating",
    action: "Review quality report",
  },
  {
    id: "RE-003",
    title: "SUP-003 Customs Clearance Delay",
    event_type: "delivery_delay",
    severity: "medium",
    supplier: "SUP-003",
    detected_at: "2024-06-08",
    status: "monitoring",
    action: "Query delivery status",
  },
];

export default function RiskEventsPage() {
  return (
    <div>
      <PageHeader
        title="Risk Event Center"
        description="Risk discovery → impact mapping → agent response. Events linked to graph seed data."
      />
      <p className="mb-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
        Demo Data: Event cards combine seed graph delivery_events / risk_events with GraphRAG links.
      </p>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {EVENTS.map((ev) => (
          <SectionCard key={ev.id} title={ev.title}>
            <div className="space-y-2 text-sm">
              <p className="text-xs text-slate-500">{ev.event_type} · {ev.detected_at}</p>
              <PermissionDecisionBadge decision={ev.severity === "high" ? "denied" : "partial"} />
              <p>Supplier: <strong>{ev.supplier}</strong></p>
              <p className="text-slate-600">{ev.action}</p>
              <div className="flex gap-2 pt-2">
                <Link href={`/supply-chain?source=${ev.supplier}`} className="text-xs text-brand-600 hover:underline">
                  View impact graph →
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
