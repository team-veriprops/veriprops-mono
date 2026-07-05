import Link from "next/link";
import { LucideIcon } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { cn } from "@lib/utils";

/** Accent tone for a metric — draws the eye to things that need attention. */
export type StatCardTone = "default" | "success" | "warning" | "danger";

const TONE: Record<StatCardTone, string> = {
  default: "text-foreground",
  success: "text-emerald-600 dark:text-emerald-400",
  warning: "text-amber-600 dark:text-amber-400",
  danger: "text-red-600 dark:text-red-400",
};

interface StatCardProps {
  label: string;
  value: number | string;
  icon?: LucideIcon;
  /** When set, the whole tile links here (e.g. a filtered queue view). */
  href?: string;
  hint?: string;
  tone?: StatCardTone;
  className?: string;
}

/**
 * A single KPI tile shared by the portal, admin and agent dashboards. Renders a
 * backend-provided count — it never derives values itself. Promoted to `ui/` because
 * all three persona home screens reuse it.
 */
export function StatCard({ label, value, icon: Icon, href, hint, tone = "default", className }: StatCardProps) {
  const body = (
    <Card
      className={cn(
        "flex h-full items-start justify-between gap-3 p-4 transition",
        href && "hover:border-primary",
        className,
      )}
    >
      <div className="min-w-0 space-y-1">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className={cn("text-2xl font-bold tabular-nums", TONE[tone])}>{value}</p>
        {hint ? <p className="text-xs text-muted-foreground">{hint}</p> : null}
      </div>
      {Icon ? <Icon className={cn("size-5 shrink-0", TONE[tone])} aria-hidden /> : null}
    </Card>
  );

  return href ? (
    <Link href={href} className="block" aria-label={label}>
      {body}
    </Link>
  ) : (
    body
  );
}
