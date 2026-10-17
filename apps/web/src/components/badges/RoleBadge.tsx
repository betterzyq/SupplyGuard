import { displayLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

const variants: Record<string, string> = {
  admin: "bg-slate-800 text-white",
  enterprise: "bg-brand-50 text-brand-700",
  procurement_manager: "bg-brand-600 text-white",
  procurement_staff: "bg-brand-100 text-brand-700",
  logistics_manager: "bg-cyan-600 text-white",
  finance_manager: "bg-emerald-600 text-white",
  quality_manager: "bg-amber-600 text-white",
  executive: "bg-violet-700 text-white",
  external_supplier: "bg-pink-600 text-white",
};

export function RoleBadge({
  role,
  className,
}: {
  role: string;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        variants[role] || "bg-slate-200 text-slate-700",
        className,
      )}
    >
      {displayLabel(role)}
    </span>
  );
}
