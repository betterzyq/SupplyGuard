import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  allowed: "bg-green-100 text-green-800 border-green-200",
  denied: "bg-red-100 text-red-800 border-red-200",
  partial: "bg-yellow-100 text-yellow-800 border-yellow-200",
  approval_required: "bg-purple-100 text-purple-800 border-purple-200",
};

export function PermissionDecisionBadge({ decision }: { decision: string }) {
  return (
    <span className={cn("rounded-full border px-2 py-0.5 text-xs font-medium", colors[decision] || "bg-slate-100")}>
      {decision}
    </span>
  );
}
