import { cn } from "@/lib/utils";

export function StatCard({
  title,
  value,
  subtitle,
  trend,
  className,
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-slate-200 bg-white p-5 shadow-card", className)}>
      <p className="text-sm font-medium text-slate-500">{title}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{value}</p>
      {subtitle && (
        <p
          className={cn(
            "mt-1 text-xs",
            trend === "up" && "text-red-600",
            trend === "down" && "text-green-600",
            !trend && "text-slate-400"
          )}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
