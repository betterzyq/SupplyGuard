import { cn } from "@/lib/utils";

const colors: Record<string, string> = {
  public: "bg-green-100 text-green-800",
  internal: "bg-blue-100 text-blue-800",
  department: "bg-yellow-100 text-yellow-800",
  confidential: "bg-orange-100 text-orange-800",
  executive: "bg-red-100 text-red-800",
};

export function SecurityLevelBadge({ level }: { level: string }) {
  return (
    <span className={cn("rounded px-2 py-0.5 text-xs font-medium", colors[level] || "bg-slate-100")}>
      {level}
    </span>
  );
}
