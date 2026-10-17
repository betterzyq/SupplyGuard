"use client";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { listBenchmarkRuns } from "@/lib/api";
import { getContracts } from "@/lib/prediction";

export default function BenchmarksPage() {
  const contracts = useQuery({
    queryKey: ["evaluation-contracts"],
    queryFn: getContracts,
  });
  const history = useQuery({
    queryKey: ["benchmark-history"],
    queryFn: () => listBenchmarkRuns(20),
  });
  return (
    <div className="space-y-5">
      <PageHeader
        title="基准评测实验"
        description="分别审计评分器、两类角色权限和历史记录；公开订单预测在独立页面验证。"
      />
      <p className="rounded-xl border border-amber-100 bg-amber-50 p-4 text-sm text-amber-800">
        历史岗位权限基准不适用于
        enterprise-v2；旧分数已废弃，不与新版本比较。历史执行入口已停用，保留记录供追溯。
      </p>
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="font-semibold">enterprise-v2 离线评分与权限检查</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          检查完整有向路径、精确引用
          precision/recall、拒绝与无证据区分，以及真实权限函数的同租户共享与跨租户拒绝。未运行在线检索、LLM
          回答质量或记忆检索实验。
        </p>
        {contracts.isPending && <p className="mt-4">正在检查…</p>}
        {contracts.isError && (
          <p role="alert" className="mt-4 text-red-600">
            检查读取失败。
            <button
              onClick={() => contracts.refetch()}
              className="ml-2 underline"
            >
              重试
            </button>
          </p>
        )}
        {contracts.data && (
          <div className="mt-5" data-testid="evaluation-contracts">
            <div className="grid gap-3 sm:grid-cols-3">
              {[
                [
                  "评分与权限契约",
                  `${contracts.data.evaluated_contracts} 项 · ${contracts.data.status === "passed" ? "全部通过" : "存在失败"}`,
                ],
                [
                  "已校正图路径金标准",
                  `${contracts.data.gold_only_cases} 题 · 尚未在线实测`,
                ],
                ["实际检索质量", "未实测，不报告准确率"],
              ].map(([a, b]) => (
                <div key={a} className="rounded-xl bg-slate-50 p-4">
                  <p className="text-xs text-slate-400">{a}</p>
                  <p className="mt-2 text-sm font-medium">{b}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 break-all text-xs leading-6 text-slate-400">
              {contracts.data.dataset_version} / {contracts.data.scorer_version}
              <br />
              数据集 SHA256 {contracts.data.dataset_sha256}
            </p>
            <details className="mt-4 text-xs">
              <summary className="cursor-pointer text-indigo-600">
                查看逐项检查与待实测金标准
              </summary>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {contracts.data.rows.map((r) => (
                  <div key={r.id} className="rounded-lg border p-3">
                    <span className="font-mono">{r.id}</span>
                    <span
                      className={`ml-3 ${r.status === "failed" ? "text-red-600" : "text-slate-400"}`}
                    >
                      {r.status === "gold_only"
                        ? "金标准 / 待在线实测"
                        : r.status === "passed"
                          ? "通过"
                          : "失败"}
                    </span>
                  </div>
                ))}
              </div>
            </details>
          </div>
        )}
      </section>
      <Link
        href="/prediction"
        className="block rounded-2xl border border-indigo-100 bg-indigo-50 p-5 text-sm text-indigo-800"
      >
        查看公开历史订单的预测基线、锁定测试集、图特征消融与失败样例 →
      </Link>
      <section className="rounded-2xl border bg-white p-5">
        <h2 className="font-semibold">历史实验记录（已废弃口径）</h2>
        <p className="mt-2 text-xs text-slate-500">
          旧结果原样保留；无法按新指标直接重算，因旧运行缺少完整观察证据。
        </p>
        {history.isError && (
          <p className="mt-3 text-sm text-red-600">历史记录读取失败。</p>
        )}
        <div className="mt-4 space-y-2">
          {history.data?.length === 0 && (
            <p className="text-sm text-slate-400">暂无历史记录。</p>
          )}
          {history.data?.map((r) => (
            <div
              key={r.id}
              className="flex flex-wrap justify-between gap-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-500"
            >
              <span>
                {r.name} · {r.mode}
              </span>
              <span>
                {r.started_at?.slice(0, 10)} · {r.status} · 历史口径
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
