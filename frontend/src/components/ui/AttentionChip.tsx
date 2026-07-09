import { ReactNode } from "react";
import Link from "next/link";
import { ArrowUpRight, LucideIcon } from "lucide-react";
import { cn } from "@lib/utils";

/** Urgency tone for an actionable signal. */
export type AttentionTone = "info" | "warning" | "danger";

const TONE_CLASS: Record<AttentionTone, string> = {
  info: "border-primary/30 bg-primary/5 text-primary",
  warning: "border-amber-500/30 bg-amber-500/5 text-amber-700 dark:text-amber-400",
  danger: "border-destructive/30 bg-destructive/5 text-destructive",
};

interface AttentionChipProps {
  icon?: LucideIcon;
  children: ReactNode;
  tone?: AttentionTone;
  /** When set, the chip links here and shows the shared link affordance. */
  href?: string;
  className?: string;
}

/**
 * A compact "needs attention" chip for backend-derived operational signals — pending
 * payouts, SLA breaches, open chargebacks. When it links to the relevant queue it carries
 * the same ArrowUpRight affordance as linked StatCards.
 */
export function AttentionChip({ icon: Icon, children, tone = "warning", href, className }: AttentionChipProps) {
  const content = (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        TONE_CLASS[tone],
        href && "transition-colors hover:brightness-95",
        className,
      )}
    >
      {Icon ? <Icon className="size-3.5 shrink-0" aria-hidden /> : null}
      {children}
      {href ? <ArrowUpRight className="size-3.5 shrink-0" aria-hidden /> : null}
    </span>
  );
  return href ? (
    <Link href={href} className="inline-flex">
      {content}
    </Link>
  ) : (
    content
  );
}
