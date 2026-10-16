import { displayLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  Supplier: "bg-violet-100 text-violet-800 border-violet-300",
  Material: "bg-cyan-100 text-cyan-800 border-cyan-300",
  Product: "bg-green-100 text-green-800 border-green-300",
  Order: "bg-orange-100 text-orange-800 border-orange-300",
  Customer: "bg-pink-100 text-pink-800 border-pink-300",
  RiskEvent: "bg-red-100 text-red-800 border-red-300",
  DeliveryEvent: "bg-yellow-100 text-yellow-800 border-yellow-300",
  QualityIssue: "bg-orange-100 text-orange-800 border-orange-300",
};

export function NodeTypeBadge({ type }: { type: string }) {
  return (
    <span className={cn("rounded border px-2 py-0.5 text-xs font-medium", colors[type] || "bg-slate-100")}>
      {displayLabel(type)}
    </span>
  );
}
