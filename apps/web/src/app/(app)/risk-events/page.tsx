"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  getBusinessOverview,
  useBusinessScenario,
  businessDate,
  moneyCny,
  riskLabels,
} from "@/lib/business";
import { useAuthStore } from "@/stores/auth";

export default function RiskEventsPage() {
  const user = useAuthStore((s) => s.user);
  const { scenarioId, selectScenario } = useBusinessScenario();
  const query = useQuery({
    queryKey: ["business-overview", user?.tenant_id, user?.id, scenarioId],
    queryFn: () => getBusinessOverview(scenarioId),
  });
  if (query.isPending)
    return <p className="text-slate-500">正在加载风险研判…</p>;
  if (query.isError)
    return (
      <p role="alert">
        风险数据不可用。
        <button onClick={() => query.refetch()} className="ml-2 underline">
          重试
        </button>
      </p>
    );
  const data = query.data;
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">风险研判</h1>
        <p className="mt-2 text-sm text-slate-500">
          从风险信号追踪关联订单，明确需要进一步核实的业务影响。
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {data.scenarios.map((s) => (
          <button
            key={s.id}
            aria-pressed={s.id === scenarioId}
            onClick={() => selectScenario(s.id)}
            className={`rounded-lg border px-4 py-2 text-sm ${s.id === scenarioId ? "border-brand-600 bg-brand-50 text-brand-700" : "bg-white text-slate-500"}`}
          >
            {s.name}
          </button>
        ))}
      </div>
      <p className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-xs leading-relaxed text-amber-800">
        模拟业务数据 · {data.provenance.dataset_version} ·{" "}
        {businessDate(data.provenance.as_of)}
        （北京时间）。关联订单由场景设定；实际缺料和延期请进入影响模拟核对。
      </p>
      {data.risk_events.map((e) => (
        <section
          key={e.id}
          className="rounded-2xl border border-slate-200 bg-white p-6"
        >
          <div className="flex flex-wrap justify-between gap-2">
            <h2 className="font-semibold text-slate-800">{e.name}</h2>
            <span className="text-xs text-orange-700">
              {riskLabels[e.severity]}
            </span>
          </div>
          <p className="mt-3 text-sm text-slate-500">{e.description}</p>
          <div className="mt-5 divide-y divide-slate-100">
            {data.orders
              .filter((o) => o.risk_event_ids.includes(e.id))
              .map((o) => (
                <div
                  key={o.id}
                  className="flex flex-wrap justify-between gap-3 py-3 text-sm"
                >
                  <span className="text-slate-700">
                    {o.id} · {o.product_name}
                  </span>
                  <span className="tabular-nums text-slate-500">
                    {moneyCny(o.amount_cny)}
                  </span>
                </div>
              ))}
          </div>
          <Link
            href={`/actions?demo_event=${e.id}&scenario=${scenarioId}`}
            className="mt-4 inline-block rounded-lg border px-3 py-2 text-sm text-indigo-600"
          >
            建立处置任务
          </Link>
          <p className="mt-3 text-xs text-slate-400">
            仅列出未交付、未取消订单；同一订单可能关联多个事件，总览金额已去重。
          </p>
        </section>
      ))}
      <Link href="/dashboard" className="inline-block text-sm text-brand-600">
        返回经营总览核对风险敞口 →
      </Link>
    </div>
  );
}
