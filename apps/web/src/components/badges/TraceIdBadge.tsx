import { cn } from "@/lib/utils";

export function TraceIdBadge({ traceId, className }: { traceId: string; className?: string }) {
  return (
    <code className={cn("rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600 font-mono", className)}>
      {traceId.slice(0, 8)}…
    </code>
  );
}
