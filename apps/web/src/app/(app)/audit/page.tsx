"use client";

import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { PermissionDecisionBadge } from "@/components/badges/PermissionDecisionBadge";
import { RoleBadge } from "@/components/badges/RoleBadge";
import { listAuditLogs, getPermissions } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

const MATRIX: Record<string, Record<string, boolean>> = {
  admin: { rag: true, graph: true, memory: true, benchmark: true, tools: true, admin: true, confidential: true },
  procurement_manager: { rag: true, graph: true, memory: true, benchmark: false, tools: true, admin: false, confidential: true },
  procurement_staff: { rag: true, graph: true, memory: true, benchmark: false, tools: true, admin: false, confidential: false },
  logistics_manager: { rag: true, graph: true, memory: true, benchmark: false, tools: true, admin: false, confidential: false },
  finance_manager: { rag: true, graph: true, memory: true, benchmark: false, tools: true, admin: false, confidential: true },
  external_supplier: { rag: true, graph: false, memory: true, benchmark: false, tools: true, admin: false, confidential: false },
};

export default function AuditPage() {
  const user = useAuthStore((s) => s.user);
  const { data: perms } = useQuery({ queryKey: ["permissions"], queryFn: getPermissions });
  const { data: audit } = useQuery({ queryKey: ["audit"], queryFn: () => listAuditLogs(30) });

  const role = user?.roles[0] || "guest";
  const matrix = MATRIX[role] || {};

  return (
    <div>
      <PageHeader title="Audit & Permission" description="RBAC matrix, security levels and permission denial events." />
      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Current Role">
          {user && <RoleBadge role={role} />}
          <p className="mt-2 text-sm text-slate-600">Max security rank: {perms?.max_security_rank}</p>
          <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
            {Object.entries(matrix).map(([feat, ok]) => (
              <div key={feat} className="flex justify-between rounded bg-slate-50 px-3 py-2">
                <span>{feat}</span>
                <PermissionDecisionBadge decision={ok ? "allowed" : "denied"} />
              </div>
            ))}
          </div>
        </SectionCard>
        <SectionCard title="Recent Audit Logs">
          <div className="max-h-96 overflow-y-auto space-y-2">
            {(audit?.items || []).map((item) => (
              <div key={item.id} className="rounded border border-slate-100 p-2 text-xs">
                <div className="flex justify-between">
                  <span className="font-mono">{item.action}</span>
                  <PermissionDecisionBadge decision={item.permission_decision} />
                </div>
                <p className="text-slate-500 mt-1">{item.reason}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
