"use client";

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { usePathname, useRouter } from "next/navigation";
import { apiClient, UserInfo } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";

const ADMIN_PATHS = [
  "/benchmarks",
  "/audit",
  "/settings",
  "/tools",
  "/traces",
  "/memory",
  "/graphrag",
];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const queries = useQueryClient();
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);
  const logout = useAuthStore((s) => s.logout);
  const [status, setStatus] = useState<
    "checking" | "ready" | "offline" | "error"
  >("checking");
  const [attempt, setAttempt] = useState(0);
  const [online, setOnline] = useState(true);
  useEffect(() => {
    const sync = () => setOnline(navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);
  const [verifiedToken, setVerifiedToken] = useState<string | null>(null);
  const token = useAuthStore((s) => s.token);
  useEffect(() => {
    let active = true;
    const stored = localStorage.getItem("sg_token");
    if (!stored) {
      logout();
      router.replace("/login");
      return;
    }
    if (!online) {
      try {
        const cached = JSON.parse(
          localStorage.getItem("sg_user") || "null",
        ) as UserInfo | null;
        const prefix = cached
          ? `sg-network-v2:${cached.tenant_id}:${cached.id}:`
          : "";
        const hasDemo =
          !!prefix &&
          Object.keys(localStorage).some((key) => key.startsWith(prefix));
        if (
          cached &&
          hasDemo &&
          cached.roles.some((r) => ["admin", "enterprise"].includes(r))
        ) {
          setAuth(stored, cached);
          setVerifiedToken(stored);
          setStatus("offline");
          return;
        }
      } catch {
        /* A corrupt cache cannot grant access. */
      }
      setStatus("error");
      return;
    }
    setStatus("checking");
    apiClient
      .get<UserInfo>("/auth/me", { timeout: 10000 })
      .then(({ data }) => {
        if (!active) return;
        if (
          !data.roles.some((role) => ["admin", "enterprise"].includes(role))
        ) {
          queries.clear();
          logout();
          router.replace("/login");
          return;
        }
        setAuth(stored, data);
        setVerifiedToken(stored);
        setStatus("ready");
      })
      .catch((error: { response?: { status?: number } }) => {
        if (!active) return;
        if ([401, 403].includes(error.response?.status || 0)) {
          queries.clear();
          logout();
          router.replace("/login");
        } else setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [token, attempt, online, logout, setAuth, router, queries]);
  if (status === "error")
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-slate-600">
        <p>暂时无法验证登录状态，请确认后端服务可用。</p>
        <button
          onClick={() => setAttempt((n) => n + 1)}
          className="rounded-lg bg-brand-600 px-4 py-2 text-white"
        >
          重新连接
        </button>
      </div>
    );
  if (
    status === "offline" &&
    !["/supply-chain", "/tracking"].includes(pathname)
  ) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-slate-600">
        <h1 className="text-xl font-semibold">离线模式仅支持合成地图演示</h1>
        <p>未验证实时登录，管理页面与写入操作不可用。</p>
        <button
          onClick={() => router.push("/supply-chain")}
          className="rounded-lg bg-brand-600 px-4 py-2 text-white"
        >
          返回离线地图
        </button>
      </div>
    );
  }
  if (
    !["ready", "offline"].includes(status) ||
    verifiedToken !== token ||
    !user
  )
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500">
        正在验证企业工作区…
      </div>
    );
  if (
    ADMIN_PATHS.some(
      (path) => pathname === path || pathname.startsWith(`${path}/`),
    ) &&
    !user.roles.includes("admin")
  ) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 text-slate-600">
        <h1 className="text-xl font-semibold">此页面仅供管理员使用</h1>
        <p>企业业务功能可在经营总览继续使用。</p>
        <button
          onClick={() => router.push("/dashboard")}
          className="rounded-lg bg-brand-600 px-4 py-2 text-white"
        >
          返回经营总览
        </button>
      </div>
    );
  }
  return <>{children}</>;
}
