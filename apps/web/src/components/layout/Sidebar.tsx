"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  BarChart3,
  Bot,
  Brain,
  FileText,
  GitBranch,
  LayoutDashboard,
  Map,
  Network,
  ScrollText,
  Settings,
  Shield,
  Wrench,
} from "lucide-react";
import { cn } from "@/lib/utils";

const nav = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/supply-chain", label: "Supply Chain Map", icon: Map },
  { href: "/risk-events", label: "Risk Events", icon: Activity },
  { href: "/rag", label: "Secure RAG", icon: Shield },
  { href: "/graphrag", label: "GraphRAG", icon: Network },
  { href: "/agent", label: "Agent Workflow", icon: Bot },
  { href: "/memory", label: "Memory", icon: Brain },
  { href: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
  { href: "/traces", label: "Observability", icon: GitBranch },
  { href: "/tools", label: "MCP Tools", icon: Wrench },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/audit", label: "Audit Logs", icon: ScrollText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-5 py-5">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-white font-bold text-sm">
            SG
          </div>
          <div>
            <p className="font-semibold text-slate-900 leading-tight">SupplyGuard</p>
            <p className="text-[10px] text-slate-500 leading-tight">Risk & Agent Harness</p>
          </div>
        </div>
      </div>
      <nav className="flex-1 overflow-y-auto p-3 space-y-0.5">
        {nav.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
