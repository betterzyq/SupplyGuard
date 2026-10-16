"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Shield, Network, GitBranch, Lock } from "lucide-react";
import { DEFAULT_PASSWORD, login, SEED_USERS } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { RoleBadge } from "@/components/badges/RoleBadge";
import { errorLabel } from "@/lib/labels";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [email, setEmail] = useState("procurement_manager@example.com");
  const [password, setPassword] = useState(DEFAULT_PASSWORD);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e?: React.FormEvent, quickEmail?: string) => {
    e?.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await login(quickEmail || email, password);
      setAuth(res.access_token, {
        ...res.user,
        id: String(res.user.id),
        tenant_id: String(res.user.tenant_id),
        supplier_id: res.user.supplier_id ? String(res.user.supplier_id) : null,
      });
      router.push("/dashboard");
    } catch (err) {
      const ax = err as { response?: { status?: number; data?: { detail?: string } }; message?: string };
      const detail = ax.response?.data?.detail;
      const msg =
        typeof detail === "string"
          ? errorLabel(detail)
          : ax.response?.status === 401
            ? "邮箱或密码错误"
            : ax.message?.includes("Network Error")
              ? "无法连接后端，请确认 make api 已启动"
              : "登录失败，请检查邮箱和密码";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen">
      {/* Left: product value */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-gradient-to-br from-slate-900 via-brand-700 to-cyan-800 p-12 text-white relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-8">
            <div className="h-12 w-12 rounded-xl bg-white/20 flex items-center justify-center font-bold text-xl">SG</div>
            <div>
              <h1 className="text-2xl font-bold">SupplyGuard</h1>
              <p className="text-sm text-white/70">供应链风险与采购决策平台</p>
            </div>
          </div>
          <p className="text-lg text-white/90 max-w-md leading-relaxed">
            识别供应商风险、追踪多跳影响、安全检索证据，并协调 AI Agent，支持可审计的采购决策。
          </p>
          <p className="mt-4 text-sm text-white/60">
            融合 Secure RAG、GraphRAG 与 Agent 工作流，辅助供应链风险决策。
          </p>
        </div>
        <div className="relative z-10 grid grid-cols-2 gap-3 max-w-md">
          {[
            { icon: Shield, label: "Secure RAG", desc: "按角色权限过滤检索结果" },
            { icon: Network, label: "GraphRAG", desc: "追踪多跳影响路径" },
            { icon: GitBranch, label: "Agent Harness", desc: "可审计的工作流" },
            { icon: Lock, label: "权限防护", desc: "工具与文档访问控制" },
          ].map(({ icon: Icon, label, desc }) => (
            <div key={label} className="rounded-lg bg-white/10 p-3 backdrop-blur">
              <Icon className="h-5 w-5 mb-1" />
              <p className="text-sm font-medium">{label}</p>
              <p className="text-xs text-white/60">{desc}</p>
            </div>
          ))}
        </div>
        {/* Abstract network lines */}
        <svg className="absolute inset-0 w-full h-full opacity-20" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          <circle cx="20%" cy="30%" r="8" fill="#ef4444" opacity="0.8" />
          <circle cx="45%" cy="50%" r="6" fill="#f97316" opacity="0.7" />
          <circle cx="70%" cy="35%" r="6" fill="#eab308" opacity="0.6" />
          <line x1="20%" y1="30%" x2="45%" y2="50%" stroke="#f97316" strokeWidth="2" />
          <line x1="45%" y1="50%" x2="70%" y2="35%" stroke="#eab308" strokeWidth="2" />
        </svg>
      </div>

      {/* Right: login form */}
      <div className="flex flex-1 flex-col justify-center px-8 py-12 lg:px-16 bg-slate-50">
        <div className="mx-auto w-full max-w-md">
          <h2 className="text-2xl font-semibold text-slate-900">登录</h2>
          <p className="mt-1 text-sm text-slate-500">使用演示账号体验不同角色的访问权限</p>

          <form onSubmit={(e) => handleLogin(e)} className="mt-8 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">邮箱</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </div>
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-medium text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {loading ? "登录中…" : "登录"}
            </button>
          </form>

          <div className="mt-8">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-3">快捷登录（演示密码：password123）</p>
            <div className="flex flex-wrap gap-2">
              {SEED_USERS.map((u) => (
                <button
                  key={u.email}
                  type="button"
                  onClick={() => handleLogin(undefined, u.email)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs hover:border-brand-300 hover:bg-brand-50 transition-colors"
                >
                  <RoleBadge role={u.role} />
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
