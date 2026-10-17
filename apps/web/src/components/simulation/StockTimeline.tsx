"use client";
import { useState } from "react";
import { simulationDay, type SimulationRun } from "@/lib/simulation";
export default function StockTimeline({
  runs,
  materialId,
}: {
  runs: { name: string; run: SimulationRun }[];
  materialId: string;
}) {
  const [active, setActive] = useState(0);
  const colors = ["#64748b", "#0891b2", "#7c3aed", "#15803d"];
  const series = runs
    .map((r, i) => ({
      ...r,
      color: colors[i],
      material: r.run.result.materials.find((m) => m.id === materialId)!,
    }))
    .filter((r) => r.material);
  if (!series.length) return null;
  const count = series[0].material.daily.length,
    day = Math.min(active, count - 1);
  const max = Math.max(
    1,
    ...series.flatMap((r) =>
      r.material.daily.map((d) => Number(d.closing_stock)),
    ),
  );
  const x = (d: number) => 48 + (d / Math.max(1, count - 1)) * 900,
    y = (n: number) => 210 - (n / max) * 176;
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-slate-800">
          库存与缺口时间线 · {series[0].material.name}
        </h3>
        <div className="flex gap-4">
          {series.map((s) => (
            <span key={s.name} className="text-xs" style={{ color: s.color }}>
              ━ {s.name}
            </span>
          ))}
        </div>
      </div>
      <svg
        role="img"
        aria-label="各方案每日结余库存折线图，可移动鼠标或点击日期查看收支"
        viewBox="0 0 980 250"
        className="mt-2 w-full"
        onMouseMove={(e) => {
          const b = e.currentTarget.getBoundingClientRect();
          setActive(
            Math.max(
              0,
              Math.min(
                count - 1,
                Math.round(
                  ((((e.clientX - b.left) / b.width) * 980 - 48) / 900) *
                    (count - 1),
                ),
              ),
            ),
          );
        }}
      >
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line
              x1={48}
              x2={948}
              y1={y(f * max)}
              y2={y(f * max)}
              stroke="#e2e8f0"
            />
            <text
              x={40}
              y={y(f * max) + 4}
              textAnchor="end"
              fill="#94a3b8"
              fontSize={11}
            >
              {Math.round(f * max)}
            </text>
          </g>
        ))}
        {series.map((s) => (
          <polyline
            key={s.name}
            points={s.material.daily
              .map((d) => `${x(d.day)},${y(Number(d.closing_stock))}`)
              .join(" ")}
            fill="none"
            stroke={s.color}
            strokeWidth={2.5}
          />
        ))}
        <line
          x1={x(day)}
          x2={x(day)}
          y1={25}
          y2={214}
          stroke="#cbd5e1"
          strokeDasharray="4 4"
        />
        {series.map((s) => (
          <circle
            key={s.name}
            cx={x(day)}
            cy={y(Number(s.material.daily[day].closing_stock))}
            r={4}
            fill={s.color}
          />
        ))}
        {[...new Set([0, Math.floor((count - 1) / 2), count - 1])].map((d) => (
          <text
            key={d}
            x={x(d)}
            y={238}
            textAnchor="middle"
            fill="#94a3b8"
            fontSize={11}
          >
            D{d + 1}
          </text>
        ))}
      </svg>
      <div className="flex flex-wrap gap-1" aria-label="选择库存明细日期">
        {Array.from({ length: count }, (_, d) => (
          <button
            key={d}
            type="button"
            aria-pressed={day === d}
            onClick={() => setActive(d)}
            className={`rounded px-2 py-1 text-[10px] ${day === d ? "bg-slate-900 text-white" : "bg-slate-50 text-slate-500"}`}
          >
            D{d + 1}
          </button>
        ))}
      </div>
      <p className="mt-3 text-xs text-slate-400">
        {simulationDay(day)} · {series[0].material.daily[day].date} · 单位：
        {series[0].material.unit}
        ；缺口为清空当日已释放生产积压仍缺少的净物料量。
      </p>
      <div className="mt-3 grid gap-3 md:grid-cols-3">
        {series.map((s) => {
          const d = s.material.daily[day];
          return (
            <div
              key={s.name}
              className="rounded-lg bg-slate-50 p-3 text-xs leading-6 text-slate-500"
            >
              <p className="font-semibold" style={{ color: s.color }}>
                {s.name}
              </p>
              <p>
                期初 {d.opening_stock} + 常规 {d.regular_receipts} + 在途{" "}
                {d.inbound_receipts} + 措施 {d.measure_receipts}
              </p>
              <p>
                消耗 {d.consumption} → 结余 {d.closing_stock}
              </p>
              <p
                className={
                  Number(d.shortage_units) > 0
                    ? "text-rose-600"
                    : "text-emerald-700"
                }
              >
                净缺口 {d.shortage_units}
              </p>
              <p className="text-[10px]">
                约束事件：{d.constraint_event_ids.join("、") || "无"}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
