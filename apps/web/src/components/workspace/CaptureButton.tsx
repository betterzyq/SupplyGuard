"use client";
import Link from "next/link";
import {
  useCommand,
  sendWorkspace,
  workspaceError,
  Entity,
} from "@/lib/workspace";
export function CaptureButton({
  kind,
  identifier,
}: {
  kind: "prediction" | "simulation";
  identifier: string;
}) {
  const capture = useCommand<
    Entity,
    { kind: string; identifier: string; share_with_tenant: true }
  >((body, key) => sendWorkspace("/captures", body, key));
  return (
    <div className="space-y-2 text-xs">
      <button
        className="rounded-lg border border-indigo-200 bg-white px-3 py-2 text-indigo-700 disabled:opacity-50"
        disabled={capture.isPending}
        onClick={() =>
          capture.mutate({ kind, identifier, share_with_tenant: true })
        }
      >
        {capture.isPending
          ? "保存中…"
          : kind === "simulation"
            ? "将此模拟快照共享到企业工作区"
            : "将此历史预测归档到企业工作区"}
      </button>
      {capture.data && (
        <Link
          className="ml-3 text-indigo-600"
          href={"/actions?record_id=" + capture.data.id}
        >
          已保存，创建处置任务 →
        </Link>
      )}
      {capture.isError && (
        <p role="alert" className="text-red-600">
          {workspaceError(capture.error)}
        </p>
      )}
      <p className="text-slate-400">
        主动归档后本企业共享；
        {kind === "simulation"
          ? "模拟金额不是实际收益，原个人快照保持私有。"
          : "公开零售验证不代表制造业迁移有效。"}
      </p>
    </div>
  );
}
