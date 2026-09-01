import { cn, humanizeEnumLabel } from "@lib/utils";

/** Semantic tone for a status/state pill. */
export type StatusTone = "positive" | "warning" | "negative" | "active" | "muted";

const TONE_CLASS: Record<StatusTone, string> = {
  positive: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  warning: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  negative: "bg-destructive/10 text-destructive",
  active: "bg-primary/10 text-primary",
  muted: "bg-muted text-muted-foreground",
};

// Backend enum values → tone. Covers the common statuses across task/verification/payment/
// payout/commission/dispute/erasure surfaces; anything unmapped falls back to muted. This
// is presentation only — comparisons in app code still use the enums themselves.
const STATUS_TONE: Record<string, StatusTone> = {
  // positive / terminal-good
  APPROVED: "positive",
  COMPLETED: "positive",
  AVAILABLE: "positive",
  CLEARED: "positive",
  PAID: "positive",
  EXECUTED: "positive",
  RESOLVED: "positive",
  ACTIVE: "positive",
  TRUSTED: "positive",
  // in-flight work
  IN_PROGRESS: "active",
  UNDER_REVIEW: "active",
  PROCESSING: "active",
  ASSIGNED: "active",
  ACCEPTED: "active",
  // needs-attention
  PENDING: "warning",
  SUBMITTED: "warning",
  PAYMENT_PENDING: "warning",
  REQUESTED: "warning",
  CLEARING: "warning",
  ON_HOLD: "warning",
  FROZEN: "warning",
  FLAGGED: "warning",
  // Meta template review states (PRD §7.7). NOT_FOUND is ours, not Meta's: declared here
  // and never submitted — the state the launch gate is really asking about, so it reads
  // as needing attention rather than as a failure.
  NOT_FOUND: "warning",
  IN_APPEAL: "warning",
  PAUSED: "warning",
  LIMIT_EXCEEDED: "warning",
  PENDING_DELETION: "muted",
  DELETED: "muted",
  ARCHIVED: "muted",
  DISABLED: "negative",
  // negative / failure
  REJECTED: "negative",
  FAILED: "negative",
  DISPUTED: "negative",
  REVERSED: "negative",
  CANCELLED: "negative",
  OVERDUE: "negative",
  SUSPENDED: "negative",
};

/** Resolve a backend status enum value to its display tone. */
export function statusTone(status: string): StatusTone {
  return STATUS_TONE[status] ?? "muted";
}

interface StatusPillProps {
  status: string;
  /** Override the resolved tone (rare — prefer the shared mapping). */
  tone?: StatusTone;
  className?: string;
}

/**
 * The canonical colored status chip: tone-coded background + humanized label. Shared by
 * finance, payouts, disputes, erasure, and the task console so every surface reads a status
 * the same way. Backend owns the value; this only styles it.
 */
export function StatusPill({ status, tone, className }: StatusPillProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        TONE_CLASS[tone ?? statusTone(status)],
        className,
      )}
    >
      {humanizeEnumLabel(status)}
    </span>
  );
}
