"use client";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, RotateCcw, MapPin } from "lucide-react";
import {
  getBusinessOverview,
  useBusinessScenario,
  moneyCny,
} from "@/lib/business";
import { useAuthStore } from "@/stores/auth";
const scenarios = [
  {
    id: "port-congestion",
    name: "港口拥堵",
    site: "SITE-NB",
    event: "EVT-PORT",
    question: "在途延误会不会耗尽库存？",
    measure: "比较加急、改道与库存缓冲，保护关键交付。",
  },
  {
    id: "tier2-shutdown",
    name: "二级供应商停产",
    site: "SITE-DG",
    event: "EVT-TIER2",
    question: "看不见的二级依赖影响哪些订单？",
    measure: "检查共同物料瓶颈与认证替代供应能力。",
  },
  {
    id: "regional-flood",
    name: "区域灾害",
    site: "SITE-WH",
    event: "EVT-FLOOD",
    question: "多个站点同时中断，如何跨区备援？",
    measure: "比较库存调拨与运力约束，避免重复计算影响。",
  },
];
export default function ShowcasePage() {
  const { scenarioId, selectScenario } = useBusinessScenario();
  const user = useAuthStore((s) => s.user);
  const [notice, setNotice] = useState("");
  const scenario = scenarios.find((s) => s.id === scenarioId) || scenarios[0];
  const query = useQuery({
    queryKey: ["scenario-overview", user?.tenant_id, user?.id, scenario.id],
    queryFn: () => getBusinessOverview(scenario.id),
    retry: false,
  });
  const suffix = `scenario=${scenario.id}`;
  const steps = [
    {
      name: "01 发现",
      text: "从风险信号和唯一订单敞口确定优先级。",
      href: "/risk-events",
      label: "查看风险信号",
    },
    {
      name: "02 定位",
      text: "在地图定位站点，查看批次、订单和业务依赖。",
      href: `/supply-chain?${suffix}&site=${scenario.site}`,
      label: "定位风险站点",
    },
    {
      name: "03 影响与方案",
      text: scenario.measure + "评估交付改善与增量成本，选择可行方案。",
      href: `/simulation?${suffix}&event=${scenario.event}`,
      label: "比较处置方案",
    },
    {
      name: "04 任务",
      text: "归档风险事件，明确责任人、期限和处置措施。",
      href: `/actions?${suffix}&demo_event=${scenario.event}`,
      label: "建立场景任务",
    },
    {
      name: "05 复盘",
      text: "提交处置结果与人工填报成本，完成验证并导出报告。",
      href: "/workspace",
      label: "导出与复盘",
    },
  ];
  return (
    <div className="mx-auto max-w-[1500px] space-y-6">
      <section className="rounded-2xl bg-slate-900 p-7 text-white">
        <p className="text-xs tracking-widest text-cyan-300">
          SUPPLYGUARD · OPERATIONS
        </p>
        <h1 className="mt-3 text-3xl font-semibold">让风险信息成为交付决策</h1>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
          连接采购、计划与物流的协同工作链：发现 → 定位 → 影响 → 方案 → 任务 →
          复盘，围绕关键物料与交付订单开展风险管理。
        </p>
        <Link
          className="mt-5 inline-flex items-center gap-2 text-sm text-cyan-200"
          href="/value"
        >
          查看商业价值 <ArrowUpRight size={16} />
        </Link>
      </section>
      <div
        className="grid gap-4 lg:grid-cols-3"
        role="group"
        aria-label="业务场景"
      >
        {scenarios.map((s) => (
          <button
            key={s.id}
            aria-pressed={scenario.id === s.id}
            onClick={() => {
              selectScenario(s.id);
              setNotice("已切换业务场景并恢复默认筛选和最新数据时点。");
            }}
            className={`rounded-2xl border p-5 text-left ${scenario.id === s.id ? "border-cyan-600 bg-cyan-50" : "border-slate-200 bg-white"}`}
          >
            <MapPin size={18} className="text-cyan-700" />
            <h2 className="mt-3 font-semibold">{s.name}</h2>
            <p className="mt-2 text-sm text-slate-500">{s.question}</p>
          </button>
        ))}
      </div>
      <section className="rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">{scenario.name} · 当前场景</h2>
          <button
            className="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"
            onClick={() => {
              selectScenario(scenario.id);
              setNotice(
                "场景视图已重置；已保存的任务、导入、报告与审计记录全部保留。",
              );
            }}
          >
            <RotateCcw size={14} />
            重置场景视图
          </button>
        </div>
        <p role="status" className="mt-2 text-xs text-cyan-700">
          {notice}
        </p>
        {query.data && (
          <p
            data-testid="story-metrics"
            className="mt-4 text-sm text-slate-600"
          >
            风险敞口 {moneyCny(query.data.metrics.exposure_amount_cny)} ·{" "}
            {query.data.metrics.at_risk_orders} 笔唯一风险订单 · 非预计损失
          </p>
        )}
        {query.isError && (
          <div role="alert" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm">
            业务服务暂不可用；场景说明仍可阅读，任务和导出需要恢复服务。
            <button className="ml-2 underline" onClick={() => query.refetch()}>
              重新加载场景
            </button>
          </div>
        )}
        <div className="mt-5 grid gap-3 lg:grid-cols-5">
          {steps.map((s) => (
            <article key={s.name} className="rounded-xl bg-slate-50 p-4">
              <h3 className="font-semibold text-slate-800">{s.name}</h3>
              <p className="mt-3 min-h-24 text-xs leading-6 text-slate-500">
                {s.text}
              </p>
              <Link
                className="mt-3 inline-flex text-xs font-medium text-cyan-700 underline"
                href={s.href}
              >
                {s.label}
              </Link>
            </article>
          ))}
        </div>
      </section>
      <details className="rounded-2xl border border-slate-200 bg-white p-5">
        <summary className="cursor-pointer text-sm text-slate-600">
          运行与分析说明
        </summary>
        <section className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border bg-white p-5">
            <h2 className="font-semibold">网络与运行环境</h2>
            <p className="mt-3 text-sm leading-7 text-slate-500">
              前端与 API
              正常运行时，地图底图、字体、轨迹、仿真和已下载的预测模型均在本地使用。浏览器完全断网后，仅已缓存的地图快照与说明可继续查看；任务、导入、导出、重新登录仍需本地服务。首次访问未缓存页面需要连接。
            </p>
            <Link
              href="/supply-chain?fallback=1"
              className="mt-3 inline-block text-xs text-cyan-700 underline"
            >
              检查地图降级列表
            </Link>
          </div>
          <div className="rounded-2xl border bg-white p-5">
            <h2 className="font-semibold">分析方法与适用范围</h2>
            <p className="mt-3 text-sm leading-7 text-slate-500">
              任务状态与交付结果分别记录。公开 DataCo
              历史验证与制造业演示分开，图特征尚未显示稳定增益。真实承运商、ERP、付费风险源和外发通知尚未接入。
            </p>
            <Link
              href="/prediction"
              className="mt-3 inline-block text-xs text-cyan-700 underline"
            >
              审阅历史模型证据
            </Link>
          </div>
        </section>
      </details>
    </div>
  );
}
