"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem("sg_token") : null;
    if (!token && !stored) {
      router.replace("/login");
    }
  }, [token, router]);

  if (!token && !user) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-500">
        加载中…
      </div>
    );
  }

  return <>{children}</>;
}
