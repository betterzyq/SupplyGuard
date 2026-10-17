"use client";
import { CaptureButton } from "@/components/workspace/CaptureButton";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Download,
  FlaskConical,
  Play,
  ShieldCheck,
} from "lucide-react";
import { businessDate, moneyCny, useBusinessScenario } from "@/lib/business";
import {
  compareSimulation,
  defaultMeasure,
  getSimulationTemplate,
  simulationDay,
  simulationError,
  type SimulationComparison,
  type SimulationInput,
  type SimulationPlan,
} from "@/lib/simulation";
import { useAuthStore } from "@/stores/auth";
import PlanEditor from "./PlanEditor";
import StockTimeline from "./StockTimeline";
const scenarios = [
  { id: "port-congestion", name: "港口拥堵" },
  { id: "tier2-shutdown", name: "二级供应商停产" },
  { id: "regional-flood", name: "区域灾害" },
];
const inputClass =
  "mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700";
function NumberControl({
  label,
  value,
  onChange,
  min = 0,
  max = 30,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="block text-xs text-slate-500">
      {label}
      <input
        type="number"
        required
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={inputClass}
      />
    </label>
  );
}
export default function SimulationWorkbench() {
  const user = useAuthStore((s) => s.user);
  const { scenarioId, selectScenario, atTime, setAtTime } =
    useBusinessScenario();
  const [initialized, setInitialized] = useState(false),
    [preset, setPreset] = useState("manufacturing"),
    [eventId, setEventId] = useState<string | null>(null);
  const [horizon, setHorizon] = useState(14),
    [duration, setDuration] = useState(7),
    [recovery, setRecovery] = useState(0),
    [eventStart, setEventStart] = useState(1),
    [capacity, setCapacity] = useState(0),
    [demand, setDemand] = useState(100);
  const [stocks, setStocks] = useState<Record<string, string>>({}),
    [supplies, setSupplies] = useState<Record<string, string>>({}),
    [inbounds, setInbounds] = useState<Record<string, number>>({});
  const [plans, setPlans] = useState<SimulationPlan[]>([]),
    [result, setResult] = useState<SimulationComparison | null>(null),
    [lastSignature, setLastSignature] = useState("");
  const [materialId, setMaterialId] = useState("MAT-01"),
    [resultPlan, setResultPlan] = useState("baseline");
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const id = params.get("scenario");
    if (scenarios.some((s) => s.id === id)) selectScenario(id!);
    const at = params.get("at");
    if (at && Number.isFinite(Date.parse(at))) setAtTime(at);
    setEventId(params.get("event"));
    if (params.get("preset") === "hand-check") setPreset("hand-check");
    setInitialized(true);
  }, []);
  const query = useQuery({
    queryKey: [
      "simulation-template-v3",
      user?.tenant_id,
      user?.id,
      scenarioId,
      preset,
      atTime,
      eventId,
    ],
    queryFn: () =>
      getSimulationTemplate({
        scenario_id: scenarioId,
        preset_id: preset,
        at_time: atTime,
        event_id: eventId,
      }),
    enabled: initialized && !!user,
    retry: false,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  });
  const mutation = useMutation({
    mutationFn: async ({
      payload,
      signature,
    }: {
      payload: { simulation: SimulationInput; plans: SimulationPlan[] };
      signature: string;
    }) => ({ comparison: await compareSimulation(payload), signature }),
    onSuccess: ({ comparison, signature }) => {
      setResult(comparison);
      setLastSignature(signature);
      setResultPlan("baseline");
    },
  });
  useEffect(() => {
    if (!query.data) return;
    const { config, default_option_ids, target_material_id } = query.data;
    setStocks(
      Object.fromEntries(config.materials.map((m) => [m.id, m.initial_stock])),
    );
    setSupplies(
      Object.fromEntries(config.supplies.map((s) => [s.id, s.receipt_per_day])),
    );
    setInbounds(
      Object.fromEntries(config.inbounds.map((l) => [l.id, l.arrival_day + 1])),
    );
    setPlans(
      default_option_ids.map((id, i) => ({
        id: `plan-${i + 1}`,
        name: `方案 ${i === 0 ? "A" : "B"}`,
        measures: [
          defaultMeasure(
            config.options.find((o) => o.id === id)!,
            preset === "hand-check",
          ),
        ],
      })),
    );
    setMaterialId(target_material_id);
    setResult(null);
    setLastSignature("");
    mutation.reset();
  }, [query.data]);
  const config = query.data?.config;
  const simulation: SimulationInput = {
    scenario_id: scenarioId,
    preset_id: preset,
    at_time: atTime,
    event_ids: config?.events.map((e) => e.id) || [],
    horizon_days: horizon,
    demand_percent: demand,
    event_overrides:
      config?.events.map((e) => ({
        event_id: e.id,
        start_day: eventStart - 1,
        duration_days: duration,
        recovery_days: recovery,
        capacity_ratio: String(capacity / 100),
      })) || [],
    material_overrides: Object.entries(stocks).map(
      ([material_id, initial_stock]) => ({ material_id, initial_stock }),
    ),
    supply_overrides: Object.entries(supplies).map(
      ([supply_id, receipt_per_day]) => ({ supply_id, receipt_per_day }),
    ),
    inbound_overrides: Object.entries(inbounds).map(([lot_id, arrival]) => ({
      lot_id,
      arrival_day: arrival - 1,
    })),
  };
  const payload = { simulation, plans },
    signature = JSON.stringify(payload),
    stale = !!result && lastSignature !== signature;
  const runs = result
    ? [
        { id: "baseline", name: "受扰基线", run: result.baseline },
        ...result.plans.map((p) => ({ id: p.id, name: p.name, run: p.run })),
      ]
    : [];
  const selectedRun = runs.find((r) => r.id === resultPlan) || runs[0];
  const changeScenario = (id: string) => {
    setEventId(null);
    selectScenario(id);
  };
  if (query.isPending || !initialized)
    return <p className="p-8 text-slate-500">正在准备制造仿真输入…</p>;
  if (query.isError || !config)
    return (
      <div
        role="alert"
        className="rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-900"
      >
        <h1 className="font-semibold">仿真输入暂不可用</h1>
        <p className="mt-3 text-sm">{simulationError(query.error)}</p>
        <button
          onClick={() => {
            setEventId(null);
            setAtTime(null);
            query.refetch();
          }}
          className="mt-4 rounded border border-amber-300 px-3 py-2 text-sm"
        >
          返回最新时点并重试
        </button>
      </div>
    );
  return (
    <div className="mx-auto max-w-[1800px] space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold tracking-[0.2em] text-slate-400">
            RESILIENCE SCENARIO LAB
          </p>
          <h1 className="mt-1 text-2xl font-semibold text-slate-900">
            影响模拟与方案比较
          </h1>
          <p className="mt-2 text-xs text-slate-500">
            把风险信号转换为库存、生产与交付约束，比较保护交付承诺所需的增量成本。
          </p>
        </div>
        <Link
          href={`/supply-chain?scenario=${scenarioId}`}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600"
        >
          返回风险控制塔 →
        </Link>
      </header>
      <div className="flex gap-3 rounded-xl border border-cyan-100 bg-cyan-50 p-4 text-xs leading-relaxed text-cyan-900">
        <FlaskConical className="mt-0.5 h-4 w-4 shrink-0" />
        <p>
          合成数据 · 确定性按日仿真。D1 为 {businessDate(config.as_of)}{" "}
          所在日期。这里只比较假设下的交付与成本，不代表真实预测精度、预计损失或实际节省收益。
        </p>
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          mutation.mutate({ payload, signature });
        }}
      >
        <fieldset
          disabled={mutation.isPending}
          className="space-y-5 disabled:opacity-70"
        >
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-800">
              <span className="rounded-md bg-slate-900 px-2 py-0.5 text-xs text-white">
                1
              </span>{" "}
              场景与扰动条件
            </div>
            <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-4">
              <label className="text-xs text-slate-500">
                仿真场景
                <select
                  aria-label="仿真场景"
                  value={scenarioId}
                  onChange={(e) => changeScenario(e.target.value)}
                  className={inputClass}
                >
                  {scenarios.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-slate-500">
                输入样例
                <select
                  aria-label="输入样例"
                  value={preset}
                  onChange={(e) => setPreset(e.target.value)}
                  className={inputClass}
                >
                  <option value="manufacturing">制造订单与多物料 BOM</option>
                  <option value="hand-check">
                    手算样例：库存 100 / 日需 20
                  </option>
                </select>
              </label>
              <label className="text-xs text-slate-500">
                模拟事件
                <select
                  aria-label="模拟事件"
                  value={eventId || ""}
                  onChange={(e) => setEventId(e.target.value || null)}
                  className={inputClass}
                >
                  <option value="">当前场景已发现的全部事件</option>
                  {query.data!.available_events.map((e) => (
                    <option key={e.id} value={e.id}>
                      {e.name}
                    </option>
                  ))}
                </select>
              </label>
              <NumberControl
                label="模拟天数"
                value={horizon}
                onChange={setHorizon}
                min={1}
                max={30}
              />
              <NumberControl
                label="事件开始日 D"
                value={eventStart}
                onChange={setEventStart}
                min={1}
                max={30}
              />
              <NumberControl
                label="停供 / 受扰天数"
                value={duration}
                onChange={setDuration}
                max={30}
              />
              <NumberControl
                label="恢复爬坡天数"
                value={recovery}
                onChange={setRecovery}
                max={30}
              />
              <NumberControl
                label="受扰期剩余产能 %"
                value={capacity}
                onChange={setCapacity}
                max={100}
              />
              <NumberControl
                label="需求规模 %"
                value={demand}
                onChange={setDemand}
                max={300}
              />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              {config.events.map((e) => (
                <span
                  key={e.id}
                  className="rounded-full bg-rose-50 px-3 py-1 text-[11px] text-rose-700"
                >
                  {e.name} · {e.site_ids.join(" / ")}
                </span>
              ))}
              {!config.events.length && (
                <p className="text-xs text-amber-700">
                  当前时点没有已发现事件，将计算无扰动输入；可返回演示最新时点后重试。
                </p>
              )}
            </div>
            <p className="mt-3 text-[11px] text-slate-400">
              上述扰动参数统一应用于所选事件；同一供给通道重叠受扰时取最小可用比例，不叠加扣减。需求按百分比向上取整，生产与供货能力保持原值。
            </p>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
              <span className="rounded-md bg-slate-900 px-2 py-0.5 text-xs text-white">
                2
              </span>{" "}
              可用库存与到货计划
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[620px] text-left text-xs">
                <thead className="text-slate-400">
                  <tr>
                    <th className="pb-3">物料</th>
                    <th>在库（件）</th>
                    <th>常规计划到货 / 日</th>
                    <th>供货上限 / 日</th>
                    <th>供给站点 / 途经</th>
                  </tr>
                </thead>
                <tbody>
                  {config.materials.map((m) => {
                    const lane = config.supplies.find(
                      (s) => s.material_id === m.id,
                    );
                    return (
                      <tr key={m.id} className="border-t border-slate-100">
                        <td className="py-3 font-medium text-slate-700">
                          {m.name}
                          <span className="mt-1 block text-[10px] text-slate-400">
                            {m.id}
                          </span>
                        </td>
                        <td className="pr-3">
                          <input
                            aria-label={`${m.id}初始库存`}
                            required
                            type="number"
                            min={0}
                            max={1000000}
                            step="0.0001"
                            value={stocks[m.id] || ""}
                            onChange={(e) =>
                              setStocks({ ...stocks, [m.id]: e.target.value })
                            }
                            className="w-24 rounded border border-slate-200 p-2"
                          />
                        </td>
                        <td className="pr-3">
                          {lane && (
                            <input
                              aria-label={`${m.id}常规日到货`}
                              required
                              type="number"
                              min={0}
                              max={lane.capacity_per_day}
                              step="0.0001"
                              value={supplies[lane.id] || ""}
                              onChange={(e) =>
                                setSupplies({
                                  ...supplies,
                                  [lane.id]: e.target.value,
                                })
                              }
                              className="w-24 rounded border border-slate-200 p-2"
                            />
                          )}
                        </td>
                        <td className="text-slate-500">
                          {lane?.capacity_per_day}
                        </td>
                        <td className="text-[10px] text-slate-400">
                          {lane?.source_site_id}
                          <br />
                          {lane?.via_site_ids.join(" → ") || "直达"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {!!config.inbounds.length && (
              <details className="mt-4 rounded-lg bg-slate-50 p-3">
                <summary className="cursor-pointer text-xs text-slate-600">
                  在途批次（与常规日到货分开，不重复计量）
                </summary>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  {config.inbounds.map((l) => (
                    <label
                      key={l.id}
                      className="text-xs leading-6 text-slate-500"
                    >
                      {l.id} · {l.quantity} 件<br />
                      计划到货日 D
                      <input
                        aria-label={`${l.id}到货日`}
                        type="number"
                        min={1}
                        max={61}
                        required
                        value={inbounds[l.id] || 1}
                        onChange={(e) =>
                          setInbounds({
                            ...inbounds,
                            [l.id]: Number(e.target.value),
                          })
                        }
                        className="ml-2 w-20 rounded border border-slate-200 p-1"
                      />
                    </label>
                  ))}
                </div>
              </details>
            )}
            <details className="mt-3 rounded-lg bg-slate-50 p-3">
              <summary className="cursor-pointer text-xs text-slate-600">
                查看 BOM 用量、生产能力与订单需求依据
              </summary>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div>
                  {Object.entries(config.bom).map(([id, children]) => (
                    <p
                      key={id}
                      className="mb-2 text-xs leading-6 text-slate-500"
                    >
                      {id} →{" "}
                      {children
                        .map((c) => `${c.component_id} × ${c.quantity}`)
                        .join(" + ")}
                    </p>
                  ))}
                </div>
                <div className="space-y-2">
                  {config.orders.map((o) => (
                    <p
                      key={o.id}
                      className="text-[11px] leading-5 text-slate-500"
                    >
                      {o.id} · {o.product_name} · 基础数量 {o.quantity}，日需{" "}
                      {o.daily_demand}，日产能 {o.daily_capacity} · D
                      {o.start_day + 1} 开始 / D{o.due_day + 1} 承诺
                    </p>
                  ))}
                </div>
              </div>
            </details>
          </section>
          <div>
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-800">
              <span className="rounded-md bg-slate-900 px-2 py-0.5 text-xs text-white">
                3
              </span>{" "}
              备选措施与增量成本
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              {plans.map((p, i) => (
                <PlanEditor
                  key={p.id}
                  plan={p}
                  options={config.options}
                  hand={preset === "hand-check"}
                  horizon={horizon}
                  onChange={(changed) =>
                    setPlans(plans.map((old, j) => (j === i ? changed : old)))
                  }
                />
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="submit"
              className="flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-medium text-white hover:bg-brand-700"
            >
              <Play className="h-4 w-4" />
              {mutation.isPending
                ? "正在计算并保存快照…"
                : "运行影响模拟并比较方案"}
            </button>
            <p className="text-xs text-slate-400">
              受扰基线 + 两个方案 · 使用同一库存和需求输入 · 不调用外部模型
            </p>
          </div>
        </fieldset>
      </form>
      {mutation.isError && (
        <div
          role="alert"
          className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"
        >
          {simulationError(mutation.error)}
        </div>
      )}
      {!result && !mutation.isPending && (
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
          设置输入并运行，查看首次缺料、延期订单、逐日收支和方案成本。
        </div>
      )}
      {result && (
        <section data-testid="simulation-results" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900">
              仿真结果与决策依据
            </h2>
            <button
              type="button"
              onClick={() => {
                const url = URL.createObjectURL(
                  new Blob([JSON.stringify(result, null, 2)], {
                    type: "application/json",
                  }),
                );
                const link = document.createElement("a");
                link.href = url;
                link.download = `SupplyGuard-simulation-${result.comparison_id.slice(0, 12)}.json`;
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
              }}
              className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600"
            >
              <Download className="h-3.5 w-3.5" />
              下载输入与结果 JSON
            </button>
          </div>
          {!stale && (
            <CaptureButton
              kind="simulation"
              identifier={result.comparison_id}
            />
          )}
          {stale && (
            <p
              role="status"
              className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800"
            >
              参数已修改，请重新运行；以下仍为上一次已保存结果。
            </p>
          )}
          <div className="grid gap-4 lg:grid-cols-3">
            {runs.map((r, i) => {
              const m = r.run.result.metrics;
              return (
                <article
                  key={r.id}
                  className={`rounded-xl border bg-white p-4 ${i === 0 ? "border-slate-200" : "border-cyan-200"}`}
                  data-testid={`simulation-${r.id}`}
                >
                  <p className="text-xs font-semibold text-slate-500">
                    {r.name}
                    {i === 0 ? " · 不新增措施" : " · 仿真方案"}
                  </p>
                  <p className="mt-3 text-[11px] text-slate-400">
                    延期订单金额（不是损失）
                  </p>
                  <p
                    className="mt-1 text-2xl font-semibold tabular-nums text-slate-900"
                    data-testid={`simulation-${r.id}-amount`}
                  >
                    {moneyCny(m.delayed_order_amount_cny)}
                  </p>
                  <div className="mt-4 grid grid-cols-2 gap-4 text-xs text-slate-500">
                    <div>
                      延期订单
                      <p className="mt-1 font-semibold text-slate-800">
                        {m.delayed_orders} 单
                      </p>
                    </div>
                    <div>
                      首次缺料
                      <p className="mt-1 font-semibold text-slate-800">
                        {simulationDay(m.first_shortage_day)}
                      </p>
                    </div>
                    <div>
                      增量成本
                      <p className="mt-1 font-semibold text-slate-800">
                        {moneyCny(m.incremental_cost_cny)}
                      </p>
                    </div>
                    <div>
                      期末未完成
                      <p className="mt-1 font-semibold text-slate-800">
                        {m.incomplete_orders} 单
                      </p>
                    </div>
                  </div>
                  {i > 0 && (
                    <p className="mt-4 rounded-lg bg-cyan-50 p-3 text-xs leading-6 text-cyan-800">
                      相对受扰基线，延期订单金额变化减少{" "}
                      {moneyCny(
                        result.plans[i - 1].delta
                          .delayed_order_amount_reduced_cny,
                      )}
                      ；该金额不是措施节省收益。
                    </p>
                  )}
                  {m.censored_orders > 0 && (
                    <p className="mt-3 text-xs text-amber-700">
                      {m.censored_orders} 单承诺日在窗口外，尚不能判断是否延期。
                    </p>
                  )}
                </article>
              );
            })}
          </div>
          <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-xs font-medium text-slate-600">
              区分规则敞口、拓扑暴露与库存约束结果
            </summary>
            <div className="mt-3 flex flex-wrap gap-6 text-sm text-slate-700">
              <span>
                P1 最新规则敞口：
                {moneyCny(result.exposure_context.p1_rule_exposure_latest_cny)}
              </span>
              <span>
                本次拓扑关联金额：
                {moneyCny(result.exposure_context.topology_order_amount_cny)}
              </span>
            </div>
            <p className="mt-3 text-xs leading-6 text-slate-400">
              {result.exposure_context.note}{" "}
              延期订单金额只按唯一订单计一次；有多条传播路径也不重复累加。
            </p>
          </details>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="text-xs text-slate-500">
              查看物料
              <select
                value={materialId}
                onChange={(e) => setMaterialId(e.target.value)}
                className="ml-2 rounded-lg border border-slate-200 bg-white px-3 py-2"
              >
                {result.baseline.result.materials.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name} · {m.id}
                  </option>
                ))}
              </select>
            </label>
            <p className="text-xs text-slate-400">
              移到折线上或点击日期，逐日核对库存守恒
            </p>
          </div>
          <StockTimeline runs={runs} materialId={materialId} />
          <section className="overflow-x-auto rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-800">
              物料缺口与缓冲
            </h3>
            <table className="w-full min-w-[620px] text-left text-xs">
              <thead className="text-slate-400">
                <tr>
                  <th className="pb-3">物料</th>
                  <th>初始库存缓冲</th>
                  {runs.map((r) => (
                    <th key={r.id}>{r.name} · 首次 / 峰值缺口</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.baseline.result.materials.map((m) => (
                  <tr
                    key={m.id}
                    className="border-t border-slate-100 text-slate-600"
                  >
                    <td className="py-3">{m.name}</td>
                    <td>
                      {m.initial_buffer_days === null
                        ? "不适用（零需求）"
                        : `${m.initial_buffer_days} 天`}
                    </td>
                    {runs.map((r) => {
                      const x = r.run.result.materials.find(
                        (a) => a.id === m.id,
                      )!;
                      return (
                        <td
                          key={r.id}
                          className={
                            Number(x.peak_shortage_units) > 0
                              ? "text-rose-600"
                              : "text-emerald-700"
                          }
                        >
                          {simulationDay(x.first_shortage_day)} /{" "}
                          {x.peak_shortage_units} 件
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-3 text-[10px] text-slate-400">
              初始缓冲 = 初始库存 /
              窗口内峰值计划日需求，供人工核算；不是包含到货后的可承诺天数。不同物料缺口不混合相加。
            </p>
          </section>
          <section className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-slate-800">
                订单影响与传播依据
              </h3>
              <select
                aria-label="订单结果方案"
                value={resultPlan}
                onChange={(e) => setResultPlan(e.target.value)}
                className="rounded-lg border border-slate-200 p-2 text-xs"
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="mt-3 space-y-2">
              {selectedRun.run.result.orders.map((o) => (
                <details
                  key={o.id}
                  className="rounded-lg border border-slate-100 p-3"
                >
                  <summary className="flex cursor-pointer flex-wrap items-center gap-3 text-xs">
                    <span className="font-medium text-slate-700">{o.id}</span>
                    <span className="text-slate-400">{o.product_name}</span>
                    <span
                      className={
                        o.delayed ? "text-rose-600" : "text-emerald-700"
                      }
                    >
                      {o.quantity === 0
                        ? "零需求"
                        : o.censored
                          ? "承诺日超出窗口"
                          : o.delayed
                            ? "未按承诺完成"
                            : "按期完成"}
                    </span>
                    <span className="ml-auto text-slate-500">
                      承诺 {simulationDay(o.due_day)} / 完成{" "}
                      {o.completed_day === null
                        ? "窗口内未完成"
                        : simulationDay(o.completed_day)}{" "}
                      · {o.produced_quantity}/{o.quantity} 件
                    </span>
                    <ArrowRight className="h-3 w-3 text-slate-400" />
                  </summary>
                  <div className="mt-3 space-y-3 text-[11px] leading-6 text-slate-500">
                    <p>
                      订单金额 {moneyCny(o.amount_cny)}；
                      {o.days_late === null
                        ? `窗口内未完成，已观测延期下界 ${o.delay_lower_bound_days} 天`
                        : `完成相对承诺偏差 ${o.days_late} 天`}
                      。使用先到期先排产顺序。
                    </p>
                    {o.evidence.length ? (
                      o.evidence.map((e) => (
                        <div
                          key={e.material_id}
                          className="rounded bg-slate-50 p-3"
                        >
                          <p>
                            {e.material_name}（每产品 {e.units_per_product}{" "}
                            件）→ {o.product_id} → {o.id}
                          </p>
                          {e.supply_paths.map((p) => (
                            <p key={p.supply_id}>
                              供给依据：
                              {[
                                p.source_site_id,
                                ...p.via_site_ids,
                                p.material_id,
                                o.product_id,
                                o.id,
                              ].join(" → ")}
                            </p>
                          ))}
                          <p>
                            生产受限日：
                            {e.blocked_days
                              .map((d) => simulationDay(d))
                              .join("、")}
                            ；关联供给约束：
                            {e.event_ids.join("、") ||
                              "无事件，检查基础库存与能力"}
                          </p>
                          {e.bom_paths.map((p, i) => (
                            <p key={i}>
                              BOM：{p.nodes.join(" → ")} · 折合用量{" "}
                              {p.units_per_product}
                            </p>
                          ))}
                        </div>
                      ))
                    ) : (
                      <p>
                        没有观测到物料阻塞；仍需结合需求释放、日产能和承诺日判断交付。
                      </p>
                    )}
                    {o.capacity_limited_days.length > 0 && (
                      <p>
                        日产能受限日：
                        {o.capacity_limited_days
                          .map((d) => simulationDay(d))
                          .join("、")}
                        ；增加库存不能消除此类产能约束。
                      </p>
                    )}
                  </div>
                </details>
              ))}
            </div>
          </section>
          <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-semibold text-slate-700">
              成本明细、执行状态与不可行原因
            </summary>
            <div className="mt-4 grid gap-4 lg:grid-cols-2">
              {result.plans.map((p) => (
                <div key={p.id}>
                  <h4 className="text-xs font-semibold text-slate-700">
                    {p.name} ·{" "}
                    {moneyCny(p.run.result.metrics.incremental_cost_cny)}
                  </h4>
                  <ul className="mt-2 space-y-1 text-[11px] leading-6 text-slate-500">
                    {p.run.result.cost_ledger.map((c, i) => (
                      <li key={i}>
                        {simulationDay(c.day)} · {c.option_id} · {c.quantity} 件
                        · {moneyCny(c.amount_cny)}
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[10px] text-slate-400">
                    执行{" "}
                    {
                      p.run.result.actions.filter((a) =>
                        ["scheduled", "rebooked"].includes(a.status),
                      ).length
                    }{" "}
                    条，受阻/等待{" "}
                    {
                      p.run.result.actions.filter((a) =>
                        ["blocked", "held"].includes(a.status),
                      ).length
                    }{" "}
                    条，窗口外未执行{" "}
                    {
                      p.run.result.actions.filter(
                        (a) => a.status === "outside_window",
                      ).length
                    }{" "}
                    条。
                  </p>
                  <details className="mt-2">
                    <summary className="cursor-pointer text-[11px] text-cyan-700">
                      展开执行记录
                    </summary>
                    <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-50 p-2 text-[10px]">
                      {JSON.stringify(p.run.result.actions, null, 2)}
                    </pre>
                  </details>
                </div>
              ))}
            </div>
          </details>
          <details className="rounded-xl border border-slate-200 bg-white p-4">
            <summary className="flex cursor-pointer items-center gap-2 text-xs font-medium text-slate-600">
              <ShieldCheck className="h-4 w-4" />
              输入快照、版本与计算假设
            </summary>
            <p className="mt-3 break-all text-[11px] text-slate-500">
              比较编号：{result.comparison_id}
              <br />
              引擎：{result.engine_version} · 数据：
              {result.baseline.input_snapshot.config.version}
            </p>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-xs leading-6 text-slate-500">
              {result.assumptions.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ol>
            <p className="mt-3 text-xs text-slate-400">
              输入与结果已保存在本项目独立快照目录，按租户及个人隔离。JSON
              可下载核对；业务处置持久化与正式报告属于后续阶段。
            </p>
          </details>
        </section>
      )}
    </div>
  );
}
