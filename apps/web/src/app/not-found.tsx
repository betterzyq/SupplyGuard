import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6 text-center">
      <p className="text-sm font-medium text-brand-600">404</p>
      <h1 className="text-2xl font-semibold text-slate-900">页面不存在</h1>
      <p className="text-sm text-slate-500">请检查访问地址，或返回总览继续使用 SupplyGuard。</p>
      <Link href="/dashboard" className="rounded-lg bg-brand-600 px-4 py-2 text-sm text-white hover:bg-brand-700">
        返回总览
      </Link>
    </main>
  );
}
