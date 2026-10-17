"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useRouter, usePathname } from "next/navigation";
import { Building2, LogOut } from "lucide-react";
import { RoleBadge } from "@/components/badges/RoleBadge";
import { useAuthStore } from "@/stores/auth";

export function Header() {
  const router = useRouter();
  const pathname = usePathname();
  const queries = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200 bg-white/90 px-6">
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Building2 className="h-4 w-4 text-slate-400" />
        制造企业工作台
        <span className="ml-2 hidden rounded-full bg-amber-50 px-2.5 py-1 text-[10px] text-amber-700 sm:inline">
          {["/workspace", "/actions"].includes(pathname)
            ? "企业数据协作"
            : pathname === "/value"
              ? "商业价值"
              : pathname === "/prediction"
                ? "公开历史验证"
                : "供应链协同"}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <details className="relative text-xs text-slate-500">
          <summary className="cursor-pointer rounded-lg border border-slate-200 px-3 py-2">
            数据说明
          </summary>
          <div className="absolute right-0 top-full z-50 mt-2 w-72 max-w-[80vw] rounded-xl border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-600 shadow-lg">
            <p>
              制造业场景中的站点、订单、轨迹与 ETA
              使用构造的演示数据，尚未接入企业 ERP 或承运商实时数据。
            </p>
            <p className="mt-2">
              企业上传记录按来源标注；预测验证使用公开 DataCo
              历史数据；方案分析为条件推演，投入产出为参数假设测算。
            </p>
          </div>
        </details>
        {user && (
          <>
            <span className="hidden text-sm text-slate-600 md:inline">
              {user.full_name}
            </span>
            <RoleBadge role={user.roles[0] || ""} />
            <button
              type="button"
              title="退出登录"
              aria-label="退出登录"
              onClick={() => {
                queries.clear();
                logout();
                router.push("/login");
              }}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-800"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </>
        )}
      </div>
    </header>
  );
}
