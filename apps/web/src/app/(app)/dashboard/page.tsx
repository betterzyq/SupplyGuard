"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  ArrowUpRight,
  AlertTriangle,
  Clock3,
  Layers3,
  ShieldCheck,
  Info,
} from "lucide-react";
import {
  getBusinessOverview,
  useBusinessScenario,
  moneyCny,
  businessDate,
  riskLabels,
  actionLabels,
} from "@/lib/business";
import { useAuthStore } from "@/stores/auth";

export default function DashboardPage() {
  const user = useAuthStore((s) => s.user);
  const { scenarioId, selectScenario } = useBusinessScenario();
  const query = useQuery({
    queryKey: ["business-overview", user?.tenant_id, user?.id, scenarioId],
    queryFn: () => getBusinessOverview(scenarioId),
  });
  if (query.isPending)
    return <p className="p-8 text-slate-500">正在加载经营总览…</p>;
  if (query.isError)
    return (
      <div
        role="alert"
        className="rounded-xl border border-red-100 bg-red-50 p-6 text-red-700"
      >
        经营数据暂不可用。
        <button onClick={() => query.refetch()} className="ml-3 underline">
          重试
        </button>
      </div>
    );
  const data = query.data;
  const metrics = [
    {
      title: "风险敞口金额",
      value: moneyCny(data.metrics.exposure_amount_cny),
      note: `${data.metrics.at_risk_orders} 笔未完成交付订单 · 非预计损失`,
      icon: AlertTriangle,
    },
    {
      title: "待处置高风险订单",
      value: `${data.metrics.pending_high_risk_orders}`,
      note: "高 / 严重风险，且尚未处置完成",
      icon: Clock3,
    },
    {
      title: "当前场景风险事件",
      value: `${data.metrics.active_risk_events}`,
      note: "截至演示时点已发现的事件",
      icon: ShieldCheck,
    },
    {
      title: "关联关键物料",
      value: `${data.metrics.critical_materials}`,
      note: "涉及的关键物料种类，尚未判断缺料",
      icon: Layers3,
    },
  ];
  return (
    <div className="mx-auto max-w-[1600px] space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs font-semibold tracking-widest text-slate-400">
            SUPPLY CHAIN INTELLIGENCE
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
            经营总览
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            看清交付风险，把有限的处置资源用在关键订单上。
          </p>
        </div>
        <span className="text-xs text-slate-400">
          演示时点 {businessDate(data.provenance.as_of)}（北京时间）
        </span>
      </div>
      <section className="relative overflow-hidden rounded-2xl bg-slate-900 p-6 text-white 2xl:p-8">
        <div className="pointer-events-none absolute -right-12 -top-20 h-64 w-64 rounded-full bg-cyan-400/10 blur-3xl" />
        <div className="relative flex flex-wrap items-start justify-between gap-6">
          <div className="max-w-2xl">
            <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-[11px] text-cyan-200">
              {data.workspace_name}
            </span>
            <h2 className="mt-5 text-xl font-medium lg:text-2xl">
              {data.scenario.decision_question}
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              {data.scenario.description}
            </p>
          </div>
          <Link
            href="/risk-events"
            className="flex items-center gap-2 rounded-xl bg-white px-4 py-2.5 text-sm font-medium text-slate-900"
          >
            查看风险研判
            <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
        <div
          className="relative mt-6 flex flex-wrap gap-2"
          role="group"
          aria-label="演示场景"
        >
          {data.scenarios.map((s) => (
            <button
              key={s.id}
              aria-pressed={scenarioId === s.id}
              onClick={() => selectScenario(s.id)}
              className={`rounded-lg border px-4 py-2 text-xs transition-colors ${scenarioId === s.id ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-100" : "border-slate-700 text-slate-400 hover:border-slate-500 hover:text-white"}`}
            >
              {s.name}
            </button>
          ))}
        </div>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ title, value, note, icon: Icon }) => (
          <section
            key={title}
            className="rounded-2xl border border-slate-200 bg-white p-5"
          >
            <div className="flex items-center justify-between text-sm text-slate-500">
              {title}
              <Icon className="h-4 w-4 text-slate-300" />
            </div>
            <p
              className="mt-4 text-2xl font-semibold tracking-tight text-slate-900"
              data-testid={
                title === "风险敞口金额" ? "exposure-value" : undefined
              }
            >
              {value}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-slate-400">
              {note}
            </p>
          </section>
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
        <section className="min-w-0 rounded-2xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-5 py-4">
            <div>
              <h2 className="font-semibold text-slate-900">
                需要关注的交付订单
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                按场景风险等级与订单金额排序 · {data.orders.length} 笔
              </p>
            </div>
            <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] text-amber-700">
              规则情景暴露
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full whitespace-nowrap text-left text-sm">
              <thead className="bg-slate-50/70 text-xs text-slate-400">
                <tr>
                  {[
                    "订单 / 客户",
                    "产品与供应来源",
                    "订单金额",
                    "交付承诺",
                    "处置状态",
                  ].map((h) => (
                    <th key={h} className="px-5 py-3 font-medium">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.orders.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-5 py-4">
                      <p className="font-medium text-slate-800">{o.id}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {o.customer}
                      </p>
                    </td>
                    <td className="px-5 py-4">
                      <p className="text-slate-700">{o.product_name}</p>
                      <p className="mt-1 text-xs text-slate-400">
                        {o.supplier_name}
                      </p>
                    </td>
                    <td className="px-5 py-4 font-medium tabular-nums text-slate-800">
                      {moneyCny(o.amount_cny)}
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500">
                      {businessDate(o.promised_at)}
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`rounded-full px-2 py-1 text-[10px] ${o.severity === "critical" ? "bg-red-50 text-red-700" : o.severity === "high" ? "bg-orange-50 text-orange-700" : "bg-amber-50 text-amber-700"}`}
                      >
                        {riskLabels[o.severity]}
                      </span>
                      <p className="mt-2 text-xs text-slate-400">
                        {actionLabels[o.action_status]}
                      </p>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <div className="space-y-4">
          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="font-semibold text-slate-900">当前风险信号</h2>
            <div className="mt-5 space-y-5">
              {data.risk_events.map((e) => (
                <div key={e.id} className="border-l-2 border-orange-300 pl-3">
                  <p className="text-sm font-medium text-slate-700">{e.name}</p>
                  <p className="mt-2 text-xs leading-relaxed text-slate-400">
                    {e.description}
                  </p>
                  <p className="mt-2 text-[10px] text-slate-400">
                    {businessDate(e.detected_at)} · {riskLabels[e.severity]}
                  </p>
                </div>
              ))}
            </div>
          </section>
          <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <p className="text-xs font-medium text-slate-500">演示供应网络</p>
            <p className="mt-3 text-sm leading-relaxed text-slate-700">
              {data.network_summary.suppliers} 家供应商 ·{" "}
              {data.network_summary.sites} 个站点
              <br />
              {data.network_summary.orders} 笔订单 ·{" "}
              {data.network_summary.shipments} 个运输批次
            </p>
            <p className="mt-3 text-xs leading-relaxed text-slate-400">
              地图、物流回放与影响模拟已就绪；公开历史订单的模型验证可在“预测验证”查看，制造业迁移尚未验证。
            </p>
          </section>
        </div>
      </div>
      <details className="rounded-2xl border border-slate-200 bg-white p-5">
        <summary className="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-slate-600">
          <Info className="h-4 w-4" />
          数据来源与指标口径（可人工核算）
        </summary>
        <div className="mt-4 space-y-3 text-xs leading-relaxed text-slate-500">
          <p>
            {data.provenance.label} · {data.provenance.dataset_version}
          </p>
          <p>{data.provenance.notice}</p>
          {Object.entries(data.definitions).map(([key, value]) => (
            <p key={key}>{value}</p>
          ))}
          <p>
            首页处置状态为固定演示记录；持久化任务请在“处置与复盘”查看。预测验证和商业假设分别提供独立证据口径。
          </p>
        </div>
      </details>
      <div className="flex flex-wrap gap-5 text-xs text-slate-500">
        <Link href="/showcase" className="text-cyan-700">
          业务场景导览 →
        </Link>
        <Link href="/value" className="text-cyan-700">
          商业价值与试点 →
        </Link>
        <Link
          href="/documents"
          className="flex items-center gap-1 hover:text-brand-600"
        >
          管理企业证据
          <ArrowRight className="h-3 w-3" />
        </Link>
        <Link
          href="/agent"
          className="flex items-center gap-1 hover:text-brand-600"
        >
          打开决策助手
          <ArrowRight className="h-3 w-3" />
        </Link>
      </div>
    </div>
  );
}
