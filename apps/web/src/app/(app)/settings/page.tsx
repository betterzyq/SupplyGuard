import { PageHeader } from "@/components/layout/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";

export default function SettingsPage() {
  return (
    <div>
      <PageHeader title="Settings" description="Environment and integration settings." />
      <SectionCard title="API Configuration">
        <p className="text-sm text-slate-600">
          API Base URL: <code className="bg-slate-100 px-2 py-0.5 rounded">{process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}</code>
        </p>
        <p className="mt-2 text-xs text-slate-400">Configure via apps/web/.env.local</p>
      </SectionCard>
    </div>
  );
}
