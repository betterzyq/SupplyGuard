"use client";
import {
  defaultMeasure,
  simulationKind,
  type SimulationOption,
  type SimulationPlan,
} from "@/lib/simulation";
export default function PlanEditor({
  plan,
  options,
  hand,
  horizon,
  onChange,
}: {
  plan: SimulationPlan;
  options: SimulationOption[];
  hand: boolean;
  horizon: number;
  onChange: (plan: SimulationPlan) => void;
}) {
  const set = (
    index: number,
    update: Partial<SimulationPlan["measures"][number]>,
  ) =>
    onChange({
      ...plan,
      measures: plan.measures.map((m, i) =>
        i === index ? { ...m, ...update } : m,
      ),
    });
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-800">{plan.name}</h3>
      <div className="mt-3 space-y-4">
        {plan.measures.map((measure, index) => {
          const option = options.find((o) => o.id === measure.option_id)!;
          if (!option) return null;
          const transport =
            option.kind === "expedite" || option.kind === "reroute";
          return (
            <div key={index} className="space-y-3 rounded-lg bg-slate-50 p-3">
              <label className="block text-xs text-slate-600">
                {plan.name}措施{index + 1}
                <select
                  aria-label={`${plan.name}措施${index + 1}`}
                  className="mt-1 w-full rounded-lg border border-slate-200 bg-white p-2 text-xs"
                  value={measure.option_id}
                  onChange={(e) =>
                    set(
                      index,
                      defaultMeasure(
                        options.find((o) => o.id === e.target.value)!,
                        hand,
                      ),
                    )
                  }
                >
                  {options.map((o) => (
                    <option
                      key={o.id}
                      value={o.id}
                      disabled={
                        !o.certified ||
                        plan.measures.some(
                          (m, i) => i !== index && m.option_id === o.id,
                        )
                      }
                    >
                      {o.name}
                    </option>
                  ))}
                </select>
              </label>
              <p className="text-[11px] leading-relaxed text-slate-500">
                {simulationKind[option.kind]} ·{" "}
                {option.certified ? "已认证 / 可用演示资源" : "未认证"} · 提前期{" "}
                {option.lead_days} 天<br />
                {option.description}
              </p>
              <div className="grid grid-cols-3 gap-2">
                <label className="text-[11px] text-slate-500">
                  {transport
                    ? "整批执行"
                    : option.kind === "alternative"
                      ? "数量 / 日"
                      : "调拨数量"}
                  <input
                    aria-label={`${plan.name}措施${index + 1}数量`}
                    type="number"
                    min={transport ? 1 : 0.0001}
                    max={transport ? 1 : option.limit_quantity}
                    step={transport ? 1 : "0.0001"}
                    required
                    readOnly={transport}
                    value={measure.quantity}
                    onChange={(e) => set(index, { quantity: e.target.value })}
                    className="mt-1 w-full rounded border border-slate-200 bg-white p-2 read-only:bg-slate-100"
                  />
                </label>
                <label className="text-[11px] text-slate-500">
                  执行日 D
                  <input
                    aria-label={`${plan.name}措施${index + 1}执行日`}
                    type="number"
                    min={1}
                    max={horizon}
                    required
                    value={measure.start_day + 1}
                    onChange={(e) =>
                      set(index, { start_day: Number(e.target.value) - 1 })
                    }
                    className="mt-1 w-full rounded border border-slate-200 p-2"
                  />
                </label>
                <label className="text-[11px] text-slate-500">
                  持续天数
                  <input
                    aria-label={`${plan.name}措施${index + 1}持续天数`}
                    type="number"
                    min={1}
                    max={option.kind === "alternative" ? 30 : 1}
                    required
                    readOnly={option.kind !== "alternative"}
                    value={measure.duration_days}
                    onChange={(e) =>
                      set(index, { duration_days: Number(e.target.value) })
                    }
                    className="mt-1 w-full rounded border border-slate-200 p-2 read-only:bg-slate-100"
                  />
                </label>
              </div>
              <p className="text-[10px] text-slate-400">
                上限 {option.limit_quantity}
                {option.kind === "alternative" ? " 件/日" : " 件"} · 增量单价 ¥
                {option.unit_cost_cny} / 件 + 固定 ¥{option.fixed_cost_cny}
                {transport && ` · 原批次 ${option.lot_id}`}
              </p>
              {plan.measures.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    onChange({
                      ...plan,
                      measures: plan.measures.filter((_, i) => i !== index),
                    })
                  }
                  className="text-xs text-rose-600"
                >
                  移除此措施
                </button>
              )}
            </div>
          );
        })}
      </div>
      {plan.measures.length < 3 &&
        options.some(
          (option) =>
            option.certified &&
            !plan.measures.some((measure) => measure.option_id === option.id),
        ) && (
          <button
            type="button"
            className="mt-3 text-xs font-medium text-cyan-700"
            onClick={() => {
              const next = options.find(
                (o) =>
                  o.certified &&
                  !plan.measures.some((m) => m.option_id === o.id),
              );
              if (next)
                onChange({
                  ...plan,
                  measures: [...plan.measures, defaultMeasure(next, hand)],
                });
            }}
          >
            + 添加组合措施
          </button>
        )}
    </section>
  );
}
