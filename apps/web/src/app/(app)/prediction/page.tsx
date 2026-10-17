"use client";
import Link from "next/link";
import { CaptureButton } from "@/components/workspace/CaptureButton";
import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  ArrowUpRight,
  Download,
  ShieldCheck,
  FlaskConical,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  getPredictionReport,
  getPredictionCases,
  predictHistorical,
  downloadPrediction,
  modelLabel,
  Metric,
} from "@/lib/prediction";
const pct = (n: number | null | undefined) =>
  n == null ? "—" : `${(n * 100).toFixed(1)}%`;
const dec = (n: number | null | undefined) => (n == null ? "—" : n.toFixed(3));
const card = "rounded-2xl border border-slate-200 bg-white p-5";

function Calibration({ metric }: { metric: Metric }) {
  const bins =
    metric.calibration?.filter(
      (b) => b.count && b.mean_probability != null && b.observed_rate != null,
    ) || [];
  return (
    <svg
      viewBox="0 0 360 235"
      role="img"
      aria-label="测试集概率校准：横轴预测概率，纵轴实际延误率"
      className="max-h-64 w-full"
    >
      {[0, 0.25, 0.5, 0.75, 1].map((v) => (
        <g key={v}>
          <line
            x1="42"
            y1={190 - v * 160}
            x2="325"
            y2={190 - v * 160}
            stroke="#e2e8f0"
          />
          <text x="8" y={194 - v * 160} fontSize="10" fill="#64748b">
            {v * 100}%
          </text>
          <text x={35 + v * 280} y="210" fontSize="10" fill="#64748b">
            {v * 100}%
          </text>
        </g>
      ))}
      <line
        x1="42"
        y1="190"
        x2="322"
        y2="30"
        stroke="#94a3b8"
        strokeDasharray="5 5"
      />
      <polyline
        points={bins
          .map(
            (b) =>
              `${42 + b.mean_probability! * 280},${190 - b.observed_rate! * 160}`,
          )
          .join(" ")}
        fill="none"
        stroke="#4f46e5"
        strokeWidth="2"
      />
      {bins.map((b) => (
        <circle
          key={b.lower}
          cx={42 + b.mean_probability! * 280}
          cy={190 - b.observed_rate! * 160}
          r="4"
          fill="#4f46e5"
        >
          <title>{`样本 ${b.count}，预测 ${pct(b.mean_probability)}，实际 ${pct(b.observed_rate)}`}</title>
        </circle>
      ))}
      <text x="130" y="230" fontSize="11" fill="#64748b">
        平均预测概率 →
      </text>
    </svg>
  );
}

export default function PredictionPage() {
  const query = useQuery({
    queryKey: ["prediction-report"],
    queryFn: getPredictionReport,
    retry: 1,
  });
  const cases = useQuery({
    queryKey: ["prediction-cases"],
    queryFn: getPredictionCases,
    retry: 1,
  });
  const [caseId, setCaseId] = useState("");
  const [group, setGroup] = useState("mode");
  const [downloadError, setDownloadError] = useState(false);
  const inference = useMutation({ mutationFn: predictHistorical });
  const download = async (name: string) => {
    setDownloadError(false);
    try {
      await downloadPrediction(name);
    } catch {
      setDownloadError(true);
    }
  };
  if (query.isPending)
    return <p className="p-8 text-slate-500">正在读取可复核的实验报告…</p>;
  if (query.isError || !query.data)
    return (
      <div className={card}>
        <h1 className="text-xl font-semibold">预测验证暂不可用</h1>
        <p className="my-4 text-slate-500">
          实验报告尚未准备好或服务暂时不可用，请联系管理员检查实验状态。
        </p>
        <button
          onClick={() => query.refetch()}
          className="rounded-lg bg-slate-900 px-4 py-2 text-white"
        >
          重新读取
        </button>
      </div>
    );
  const r = query.data;
  const m = r.models[r.selection.name].test;
  const ci = r.uncertainty.intervals;
  return (
    <div className="space-y-5" data-testid="prediction-page">
      <PageHeader
        title="预测验证"
        description="用可复现的公开历史订单，检验提前识别延误的能力；为制造企业后续试点建立评估依据。"
      />
      <section className="rounded-2xl bg-slate-900 p-6 text-white">
        <div className="flex flex-wrap items-center gap-2 text-xs text-indigo-200">
          <FlaskConical className="h-4 w-4" /> PUBLIC DATA VALIDATION{" "}
          <span className="rounded-full bg-white/10 px-3 py-1">
            公开零售历史数据
          </span>
          <span className="rounded-full bg-white/10 px-3 py-1">
            制造业迁移尚未验证
          </span>
        </div>
        <div className="mt-5 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div>
            <h2 className="text-2xl font-semibold">
              把有限的跟进精力，放在更可能延误的订单上
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">
              预测时点为下单时。比较同一批测试订单上的历史率、业务规则、机器学习和金额排序；风险概率仅适用于本页
              DataCo 历史验证样例。
            </p>
          </div>
          <div className="rounded-xl bg-white/5 p-4 text-sm">
            <p className="text-slate-400">验证集选定模型</p>
            <p className="mt-2 font-medium" data-testid="selected-model">
              {modelLabel(r.selection.name)}
            </p>
            <p className="mt-2 text-xs text-slate-400">
              阈值 {pct(r.selection.threshold)} · 测试集不参与选型
            </p>
            <p className="mt-2 break-all text-[10px] text-slate-500">
              版本 {r.model_version}
            </p>
          </div>
        </div>
      </section>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["测试集 AP", pct(m.average_precision), "平均精确率；与下方基线比较"],
          [
            "优先跟进前 10%",
            pct(m.ranking["10"].recall),
            `覆盖延误订单；跟进 ${m.ranking["10"].k.toLocaleString()} 单`,
          ],
          [
            "测试订单",
            m.count.toLocaleString(),
            `延误占比 ${pct(m.positive_rate)}`,
          ],
          ["概率校准误差", dec(m.ece), "ECE 越低越好；不表示业务损失"],
        ].map(([label, value, detail]) => (
          <div className={card} key={label}>
            <p className="text-xs text-slate-500">{label}</p>
            <p
              className="mt-3 text-3xl font-semibold tracking-tight"
              data-testid={label === "测试集 AP" ? "test-ap" : undefined}
            >
              {value}
            </p>
            <p className="mt-2 text-xs text-slate-400">{detail}</p>
          </div>
        ))}
      </div>
      <section className={card}>
        <h2 className="font-semibold">同一测试集上的模型与业务基线</h2>
        <p className="mt-2 text-xs leading-5 text-slate-500">
          AP 为 average precision，不是梯形积分 PR 面积。前 10%
          的名额固定，按分数降序、同分按固定时间顺序排列。金额排序只用于排队，不输出概率或校准分数。原数据币种未注明，不换算人民币。
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full whitespace-nowrap text-left text-xs">
            <thead className="border-b text-slate-500">
              <tr>
                {[
                  "方法",
                  "验证 AP",
                  "测试 AP",
                  "前10% 召回",
                  "前10% 精确率",
                  "延误金额覆盖",
                  "Brier",
                ].map((h) => (
                  <th key={h} className="p-3 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(r.models).map(([name, { test: t }]) => (
                <tr
                  key={name}
                  className={`border-b border-slate-100 ${name === r.selection.name ? "bg-indigo-50" : ""}`}
                >
                  <td className="p-3">
                    {modelLabel(name)}
                    {name === r.selection.name && (
                      <span className="ml-2 text-indigo-600">已选</span>
                    )}
                  </td>
                  <td className="p-3">
                    {pct(
                      r.candidates.find((c) => c.name === name)?.validation_ap,
                    )}
                  </td>
                  <td className="p-3">{pct(t.average_precision)}</td>
                  <td className="p-3">{pct(t.ranking["10"].recall)}</td>
                  <td className="p-3">{pct(t.ranking["10"].precision)}</td>
                  <td className="p-3">
                    {pct(t.ranking["10"].late_quoted_amount_capture)}
                  </td>
                  <td className="p-3">{dec(t.brier)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 rounded-lg bg-slate-50 p-3 text-xs leading-5 text-slate-600">
          同样跟进前10%，模型延误金额覆盖{" "}
          {pct(m.ranking["10"].late_quoted_amount_capture)}；金额排序覆盖{" "}
          {pct(
            r.models.quoted_amount_ranking.test.ranking["10"]
              .late_quoted_amount_capture,
          )}
          。请按识别延误订单数量或保护金额的目标选择策略，AP提高不代表金额覆盖或实际收益提高。
        </p>
        <p className="mt-4 text-xs text-slate-500">
          图特征消融：基础 {modelLabel(r.ablation.base)} → 历史{" "}
          {modelLabel(r.ablation.history)} → 图结构{" "}
          {modelLabel(r.ablation.graph)}
          。每组选型只看验证集，测试表现均如实保留。
        </p>
      </section>
      <div className="grid gap-5 lg:grid-cols-2">
        <section className={card}>
          <h2 className="font-semibold">概率是否可信</h2>
          <Calibration metric={m} />
          {m.confusion && (
            <p className="mb-3 rounded-lg bg-amber-50 p-3 text-xs leading-5 text-amber-800">
              冻结阈值会标记{" "}
              {(m.confusion.tp + m.confusion.fp).toLocaleString()} /{" "}
              {m.count.toLocaleString()} 单，其中误报{" "}
              {m.confusion.fp.toLocaleString()}{" "}
              单。该阈值仅用于本实验评估，实际跟进需结合名额与误报成本。
            </p>
          )}
          <p className="text-xs text-slate-500">
            对角线为理想校准。Brier {dec(m.brier)}；冻结阈值下 Precision{" "}
            {pct(m.precision)} / Recall {pct(m.recall)}
            。没有在测试集上调阈值或重新校准。
          </p>
        </section>
        <section className={card}>
          <h2 className="font-semibold">结论有多稳定</h2>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            按订单日历周分块重采样 {r.uncertainty.resamples}{" "}
            次，保留周内相关性，提供 95% 百分位区间。
          </p>
          <dl className="mt-5 space-y-4 text-sm">
            {[
              ["AP 区间", "average_precision"],
              ["前10% 召回区间", "recall_at_10"],
              ["AP 相对金额排序的差值", "ap_delta_vs_amount"],
              ["AP 相对固定规则的差值", "ap_delta_vs_fixed_rule"],
              ["AP 相对基础 LightGBM 的差值", "ap_delta_vs_base_lightgbm"],
            ].map(([label, key]) => (
              <div
                key={key}
                className="flex justify-between gap-3 border-b pb-3"
              >
                <dt className="text-slate-500">{label}</dt>
                <dd>
                  {pct(ci[key].low)} ～ {pct(ci[key].high)}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-xs leading-5 text-slate-400">
            区间反映这段历史样本的不确定性；无法证明对制造企业、未来业务或因果收益同样有效。
          </p>
        </section>
      </div>
      <section className={card}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-semibold">不同业务群体表现</h2>
          <select
            aria-label="分组维度"
            value={group}
            onChange={(e) => setGroup(e.target.value)}
            className="rounded-lg border p-2 text-xs"
          >
            <option value="mode">运输服务</option>
            <option value="market">市场</option>
            <option value="month">月份</option>
          </select>
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Object.entries(r.subgroups[group]).map(([name, t]) => (
            <div key={name} className="rounded-xl bg-slate-50 p-3 text-xs">
              <p className="font-medium">{name}</p>
              <p className="mt-2 text-slate-500">
                {t.count.toLocaleString()} 单 · 延误 {pct(t.positive_rate)}
              </p>
              <p className="mt-2">
                AP {pct(t.average_precision)} · ECE {dec(t.ece)}
              </p>
            </div>
          ))}
        </div>
      </section>
      <section className={card}>
        <h2 className="font-semibold">复核一笔历史预测</h2>
        <p className="mt-2 text-xs text-slate-500">
          样例由固定等间隔抽样和最早的误报、漏报组成。订单号已脱敏；实际标签仅供事后核对，未进入预测特征。
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <select
            aria-label="历史订单样例"
            value={caseId}
            onChange={(e) => {
              setCaseId(e.target.value);
              inference.reset();
            }}
            className="min-w-0 max-w-full rounded-lg border p-2 text-sm"
          >
            <option value="">选择历史订单</option>
            {cases.data?.map((c) => (
              <option key={c.case_id} value={c.case_id}>
                {c.placed.slice(0, 10)} · {c.case_id.slice(0, 10)}
                {r.failure_cases.some((f) => f.case_id === c.case_id)
                  ? " · 错误样例"
                  : ""}
              </option>
            ))}
          </select>
          <button
            disabled={!caseId || inference.isPending}
            onClick={() => inference.mutate(caseId)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white disabled:opacity-40"
          >
            {inference.isPending ? "计算中…" : "运行历史样例预测"}
          </button>
        </div>
        {cases.isError && (
          <p role="alert" className="mt-3 text-sm text-red-600">
            样例读取失败，请刷新重试。
          </p>
        )}
        {inference.isError && (
          <p role="alert" className="mt-3 text-sm text-red-600">
            预测未成功，请重试或联系管理员检查实验文件。
          </p>
        )}
        {inference.data && (
          <CaptureButton
            kind="prediction"
            identifier={inference.data.case_id}
          />
        )}
        {inference.data && (
          <div
            className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50 p-4 text-sm"
            data-testid="prediction-result"
          >
            <p>
              延误概率 <strong>{pct(inference.data.probability)}</strong> · 阈值{" "}
              {pct(inference.data.threshold)} · 实际结果{" "}
              {inference.data.observed_label_for_review ? "延误" : "未延误"}
            </p>
            <p className="mt-2 text-xs text-slate-500">
              特征依据：下单时计划运输 {inference.data.features.planned_min}{" "}
              天、篮子金额{" "}
              {Number(inference.data.features.quoted_amount).toFixed(2)}{" "}
              原始单位、成熟历史率{" "}
              {pct(Number(inference.data.features.history_rate))}、历史图结构。
            </p>
            {inference.data.unknown_categories.length > 0 && (
              <p className="mt-2 text-amber-700">
                出现训练未见类别：{inference.data.unknown_categories.join(", ")}
                ；需谨慎使用。
              </p>
            )}
            <p className="mt-2 break-all text-[10px] text-slate-400">
              {inference.data.model_version}
            </p>
          </div>
        )}
      </section>
      <section className={card}>
        <div className="flex items-center gap-2 font-semibold">
          <ShieldCheck className="h-4 w-4 text-teal-600" /> 数据、切分与复现证据
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          {Object.entries(r.splits).map(([name, s]) => (
            <div key={name} className="rounded-xl border p-3 text-xs">
              <p className="font-semibold">
                {
                  (
                    {
                      train: "训练集",
                      validation: "验证集",
                      test: "锁定测试集",
                    } as Record<string, string>
                  )[name]
                }
              </p>
              <p className="mt-2">
                {s.count.toLocaleString()} 单 · 延误 {pct(s.positive_rate)}
              </p>
              <p className="mt-1 text-slate-400">
                {s.min_time.slice(0, 10)} — {s.max_time.slice(0, 10)}
              </p>
              <p className="mt-2 break-all text-[10px] text-slate-400">
                订单清单 SHA256 {s.ids_sha256}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs leading-6 text-slate-500">
          原始 {r.audit.raw_items.toLocaleString()} 行 /{" "}
          {r.audit.raw_orders.toLocaleString()} 单；取消与疑似欺诈排除{" "}
          {r.audit.excluded_cancel_fraud_orders.toLocaleString()}{" "}
          单；其他无效订单 {r.audit.excluded_other_invalid_orders}{" "}
          单；订单跨集合交集 {r.audit.same_order_overlap}
          。标签可用时间为保守假设：发运时间与下单加实际天数的较晚者，再加 7
          天。缺少真实数据入库日志。
        </p>
        <p className="mt-3 text-xs text-slate-500">
          来源：
          <a
            className="text-indigo-600 underline"
            href={r.source.source}
            target="_blank"
            rel="noreferrer"
          >
            DataCo v5 · DOI {r.source.doi}
          </a>{" "}
          · {r.source.license} · {r.source.contributors.join(" / ")}
          。仅下载结构化订单与字段说明，未使用点击流和客户个人字段。
        </p>
        <p className="mt-3 break-all text-[10px] text-slate-400">
          协议 {r.protocol_version} · SHA256 {r.protocol_sha256}
          <br />
          数据 SHA256 {r.source_sha256}
        </p>
        <div className="mt-4 flex flex-wrap gap-2">
          {[
            ["完整评测 JSON", "report.json"],
            ["切分清单", "split-manifest.json"],
            ["数据审计", "audit.json"],
            ["冻结协议", "protocol.json"],
            ["PR 曲线", "precision-recall.png"],
            ["校准图", "calibration.png"],
          ].map(([label, name]) => (
            <button
              key={name}
              onClick={() => download(name)}
              className="flex items-center gap-2 rounded-lg border px-3 py-2 text-xs"
            >
              <Download className="h-3 w-3" />
              {label}
            </button>
          ))}
        </div>
        {downloadError && (
          <p role="alert" className="mt-2 text-sm text-red-600">
            下载失败，请重试。
          </p>
        )}
      </section>
      <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
        制造场景继续使用明确标注的模拟传播与方案比较。
        <Link
          className="inline-flex items-center text-indigo-600"
          href="/simulation"
        >
          前往影响模拟
          <ArrowUpRight className="h-3 w-3" />
        </Link>
      </p>
    </div>
  );
}
