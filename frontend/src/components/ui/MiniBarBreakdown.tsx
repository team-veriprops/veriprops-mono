import { StatusPill, statusTone, StatusTone } from "./StatusPill";
import { cn } from "@lib/utils";

const BAR_CLASS: Record<StatusTone, string> = {
  positive: "bg-emerald-500/60",
  warning: "bg-amber-500/60",
  negative: "bg-destructive/60",
  active: "bg-primary/60",
  muted: "bg-muted-foreground/40",
};

interface MiniBarBreakdownProps {
  /** Backend-provided status → count map (e.g. FinanceSummary.paymentsByStatus). */
  counts: Record<string, number>;
  emptyText?: string;
  className?: string;
}

/**
 * A compact status distribution: one tone-coded bar per status, sized to its share of the
 * total, with a StatusPill label and count. Dependency-free CSS bars (the same approach as
 * the analytics charts). Backend owns the counts — this only visualizes them.
 */
export function MiniBarBreakdown({ counts, emptyText = "None yet.", className }: MiniBarBreakdownProps) {
  const entries = Object.entries(counts);
  const total = entries.reduce((sum, [, n]) => sum + n, 0);
  if (entries.length === 0 || total === 0) {
    return <p className="text-xs text-muted-foreground">{emptyText}</p>;
  }
  return (
    <ul className={cn("space-y-2", className)}>
      {entries.map(([status, count]) => {
        const tone = statusTone(status);
        return (
          <li key={status} className="flex items-center gap-3 text-sm">
            <StatusPill status={status} className="w-28 shrink-0 justify-center" />
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full", BAR_CLASS[tone])}
                style={{ width: `${Math.max(3, (count / total) * 100)}%` }}
              />
            </div>
            <span className="w-8 shrink-0 text-right font-medium tabular-nums">{count}</span>
          </li>
        );
      })}
    </ul>
  );
}
