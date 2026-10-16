"use client";

import { displayLabel } from "@/lib/labels";
import { useRouter } from "next/navigation";
import { LogOut, Server } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { RoleBadge } from "@/components/badges/RoleBadge";
import { getHealthDependencies } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

export function Header() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const { data: health } = useQuery({
    queryKey: ["health-deps"],
    queryFn: getHealthDependencies,
    refetchInterval: 60_000,
  });

  const llm = health?.dependencies?.llm;

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-6">
      <div className="flex items-center gap-4 text-sm text-slate-500">
        <span className="flex items-center gap-1.5">
          <Server className="h-4 w-4" />
          API:{" "}
          <span className={health?.status === "ok" ? "text-green-600" : "text-amber-600"}>
            {health ? displayLabel(health.status) : "检查中…"}
          </span>
        </span>
        {llm?.model && (
          <span className="hidden md:inline text-slate-400">
            LLM: {llm.provider || "deepseek"} / {llm.model}
          </span>
        )}
        <span className="hidden lg:inline rounded bg-slate-100 px-2 py-0.5 text-xs">开发环境</span>
      </div>
      <div className="flex items-center gap-3">
        {user && (
          <>
            <div className="text-right hidden sm:block">
              <p className="text-sm font-medium text-slate-900">{user.full_name}</p>
              <p className="text-xs text-slate-500">{user.email}</p>
            </div>
            {user.roles[0] && <RoleBadge role={user.roles[0]} />}
            <button
              type="button"
              onClick={() => {
                logout();
                router.push("/login");
              }}
              className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:bg-slate-50 hover:text-slate-700"
              title="退出登录"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </>
        )}
      </div>
    </header>
  );
}
