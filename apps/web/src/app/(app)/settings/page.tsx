import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";

export default function SettingsPage() {
  return (
    <div>
      <PageHeader title="设置" description="查看运行环境与服务集成配置。" />
      <SectionCard title="API 配置">
        <p className="text-sm text-slate-600">
          API 基础地址：<code className="bg-slate-100 px-2 py-0.5 rounded">{process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1（通过前端同源代理）"}</code>
        </p>
        <p className="mt-2 text-xs text-slate-400">通过 apps/web/.env.local 配置</p>
      </SectionCard>
    </div>
  );
}
