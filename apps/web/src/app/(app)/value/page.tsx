"use client";
import Link from "next/link";
import { useState } from "react";
import { moneyCny } from "@/lib/business";
const defaults = {
  people: 4,
  hours: 3,
  rate: 100,
  weeks: 48,
  adoption: 50,
  subscription: 48000,
  integration: 20000,
  operation: 12000,
};
const labels: Record<keyof typeof defaults, string> = {
  people: "参与人数",
  hours: "每人每周可节省工时",
  rate: "每小时综合人工成本（元）",
  weeks: "年度工作周数",
  adoption: "实际采用比例（%）",
  subscription: "年度订阅成本假设（元）",
  integration: "首年接入成本假设（元）",
  operation: "年度运维与情报成本（元）",
};
export default function ValuePage() {
  const [input, setInput] = useState<Record<keyof typeof defaults, string>>(
    Object.fromEntries(
      Object.entries(defaults).map(([k, v]) => [k, String(v)]),
    ) as Record<keyof typeof defaults, string>,
  );
  const n = (k: keyof typeof defaults) => Number(input[k]);
  const valid =
    Object.values(input).every(
      (v) =>
        v.trim() !== "" &&
        Number.isFinite(Number(v)) &&
        Number(v) >= 0 &&
        Number(v) <= 1e9,
    ) &&
    n("adoption") <= 100 &&
    n("weeks") <= 53 &&
    n("hours") <= 168 &&
    n("people") <= 100000 &&
    Number.isInteger(n("people"));
  const benefit = valid
    ? (n("people") * n("hours") * n("rate") * n("weeks") * n("adoption")) / 100
    : 0;
  const cost = valid
    ? n("subscription") + n("integration") + n("operation")
    : 0;
  const result = {
    type: "assumption_only",
    currency: "CNY",
    input,
    annual_labor_value: benefit,
    first_year_cost: cost,
    first_year_net: benefit - cost,
    first_year_roi: cost > 0 ? (benefit - cost) / cost : null,
    notice:
      "假设测算；工时价值不等于现金节省，不含订单金额、避免损失或未经验证的模型收益。",
  };
  const download = () => {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(result, null, 2)], { type: "application/json" }),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "supplyguard-business-assumptions.json";
    a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="mx-auto max-w-[1500px] space-y-6">
      <section className="rounded-2xl bg-slate-900 p-7 text-white">
        <p className="text-xs tracking-widest text-cyan-300">
          BUSINESS VALUE · 制造业供应链决策
        </p>
        <h1 className="mt-3 text-3xl font-semibold">
          从风险敞口，到可审计的处置
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
          面向存在关键物料、多级供应依赖与跨区运输的电子及装备制造团队，让采购、计划、物流共同判断哪些订单值得优先投入资源。
        </p>
        <Link
          href="/showcase"
          className="mt-4 inline-block text-sm text-cyan-200 underline"
        >
          查看业务场景
        </Link>
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        {[
          [
            "谁使用、谁购买",
            "使用者：采购、物流、计划及供应链负责人。购买发起人：供应链总监；预算评估：财务与管理层；数据和部署评估：IT。",
          ],
          [
            "先解决什么",
            "风险信息散落，难以追溯关键订单；单点依赖不可见，方案成本难对比；处置缺乏责任人与复盘证据。围绕异常响应时间、任务闭环率和数据覆盖率开展协同管理。",
          ],
          [
            "平台如何交付",
            "建议按站点/供应商规模与功能订阅，企业 API 作为扩展；本地或私有部署另计接入、运维和数据源成本。当前交付本地平台与工作区 API，计费、SLA、托管多企业服务仍需建设。",
          ],
        ].map(([title, text]) => (
          <article key={title} className="rounded-2xl border bg-white p-5">
            <h2 className="font-semibold">{title}</h2>
            <p className="mt-3 text-sm leading-7 text-slate-500">{text}</p>
          </article>
        ))}
      </div>
      <section className="rounded-2xl border border-cyan-200 bg-white p-5">
        <h2 className="text-lg font-semibold">投入产出假设测算</h2>
        <p className="mt-2 text-sm text-slate-500">
          所有默认数值均为可编辑示例，不是报价或客户业绩。年度人工价值 = 人数 ×
          工时 × 时薪 × 周数 × 采用比例。工时释放不一定转化为现金节省。
        </p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {(Object.keys(defaults) as (keyof typeof defaults)[]).map((k) => (
            <label key={k} className="text-xs text-slate-500">
              {labels[k]}
              <input
                className="mt-2 w-full rounded-lg border p-2 text-sm text-slate-800"
                type="number"
                min="0"
                step={k === "people" ? "1" : "any"}
                value={input[k]}
                onChange={(e) => setInput({ ...input, [k]: e.target.value })}
              />
            </label>
          ))}
        </div>
        {!valid ? (
          <p role="alert" className="mt-4 text-sm text-red-700">
            请输入有效非负数；人数须为整数且不超过10万，周数≤53、每周工时≤168、采用比例≤100%。
          </p>
        ) : (
          <div
            data-testid="business-case-result"
            className="mt-5 grid gap-4 rounded-xl bg-slate-50 p-5 sm:grid-cols-4"
          >
            {[
              ["年度人工价值假设", moneyCny(benefit)],
              ["首年总投入假设", moneyCny(cost)],
              ["首年净值假设", moneyCny(benefit - cost)],
              [
                "首年 ROI 假设",
                cost > 0
                  ? `${(((benefit - cost) / cost) * 100).toFixed(1)}%`
                  : "N/A（投入为0）",
              ],
            ].map(([a, b]) => (
              <div key={a}>
                <p className="text-xs text-slate-500">{a}</p>
                <p className="mt-2 text-xl font-semibold">{b}</p>
              </div>
            ))}
          </div>
        )}
        <p className="mt-4 text-xs leading-6 text-slate-500">
          默认假设：人工价值28,800元，首年投入80,000元，首年净值−51,200元，ROI
          −64%。未纳入订单敞口、避免损失或模型预测收益。市场规模需取得可核验客户清单、预算和访谈证据后估计，当前不展示
          TAM 数字。
        </p>
        <button
          disabled={!valid}
          onClick={download}
          className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-40"
        >
          下载当前测算假设
        </button>
      </section>
    </div>
  );
}
