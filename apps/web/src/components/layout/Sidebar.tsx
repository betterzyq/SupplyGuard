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
  Truck,
  FlaskConical,
  ChevronDown,
  Presentation,
  BriefcaseBusiness,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth";

const businessNav = [
  { href: "/showcase", label: "业务场景", icon: Presentation },
  { href: "/value", label: "商业价值", icon: BriefcaseBusiness },
  { href: "/dashboard", label: "经营总览", icon: LayoutDashboard },
  { href: "/risk-events", label: "风险研判", icon: Activity },
  { href: "/supply-chain", label: "风险控制塔", icon: Map },
  { href: "/tracking", label: "物流跟踪", icon: Truck },
  { href: "/simulation", label: "影响模拟", icon: FlaskConical },
  { href: "/prediction", label: "预测验证", icon: BarChart3 },
  { href: "/actions", label: "处置与复盘", icon: ScrollText },
  { href: "/workspace", label: "企业数据", icon: FileText },
  { href: "/agent", label: "决策助手", icon: Bot },
  { href: "/rag", label: "证据检索", icon: Shield },
  { href: "/documents", label: "企业知识库", icon: FileText },
];
const developerNav = [
  { href: "/graphrag", label: "图谱查询", icon: Network },
  { href: "/memory", label: "记忆管理", icon: Brain },
  { href: "/benchmarks", label: "基准评测", icon: BarChart3 },
  { href: "/traces", label: "链路诊断", icon: GitBranch },
  { href: "/tools", label: "工具调试", icon: Wrench },
  { href: "/audit", label: "审计日志", icon: ScrollText },
  { href: "/settings", label: "系统配置", icon: Settings },
];
export function Sidebar() {
  const pathname = usePathname();
  const user = useAuthStore((s) => s.user);
  const renderLinks = (items: typeof businessNav) =>
    items.map(({ href, label, icon: Icon }) => (
      <Link
        key={href}
        href={href}
        className={cn(
          "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
          pathname === href
            ? "bg-brand-600 text-white shadow-sm"
            : "text-slate-500 hover:bg-slate-100 hover:text-slate-900",
        )}
      >
        <Icon className="h-4 w-4 shrink-0" />
        <span>{label}</span>
      </Link>
    ));
  return (
    <aside className="flex w-52 shrink-0 flex-col border-r border-slate-200 bg-white xl:w-60">
      <Link href="/dashboard" className="flex items-center gap-3 px-5 py-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 font-bold text-white">
          SG
        </div>
        <div>
          <p className="font-semibold tracking-tight text-slate-900">
            SupplyGuard
          </p>
          <p className="mt-1 text-[10px] text-slate-500">
            供应链风险与韧性决策
          </p>
        </div>
      </Link>
      <nav
        aria-label="主导航"
        className="flex-1 space-y-1 overflow-y-auto px-3"
      >
        <p className="px-3 pb-2 pt-3 text-[10px] font-semibold tracking-[0.16em] text-slate-400">
          企业工作台
        </p>
        {renderLinks(businessNav)}
        {user?.roles.includes("admin") && (
          <details
            className="pt-5"
            open={developerNav.some((item) => item.href === pathname)}
          >
            <summary className="flex cursor-pointer list-none items-center justify-between px-3 py-2 text-xs text-slate-500">
              开发与运维
              <ChevronDown className="h-3 w-3" />
            </summary>
            <div className="mt-1 space-y-1">{renderLinks(developerNav)}</div>
          </details>
        )}
      </nav>
      <div className="m-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
        <p className="text-xs font-medium text-slate-700">制造企业工作区</p>
        <p className="mt-1 text-[10px] leading-relaxed text-slate-400">
          订单 · 供应网络 · 协同处置
          <br />
          供应链风险与韧性决策
        </p>
      </div>
    </aside>
  );
}
