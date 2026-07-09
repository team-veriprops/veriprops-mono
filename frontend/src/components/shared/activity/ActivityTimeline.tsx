"use client";

import { Loader2, Activity } from "lucide-react";
import { humanizeEnumLabel } from "@lib/utils";
import { AuditActivityEvent } from "@/types/audit";

interface ActivityTimelineProps {
  events: AuditActivityEvent[];
  isLoading: boolean;
  isError: boolean;
  emptyLabel?: string;
}

/**
 * PII-safe transition timeline (§19.2/§19.3). Renders backend-owned audit events —
 * action, state change and timestamp only, never an actor identity. Shared by the
 * customer verification-activity view and the agent task-history view.
 */
export function ActivityTimeline({ events, isLoading, isError, emptyLabel }: ActivityTimelineProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-12 justify-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        <Loader2 className="w-5 h-5 animate-spin" /> Loading activity…
      </div>
    );
  }
  if (isError) {
    return (
      <p className="py-12 text-center text-sm" style={{ color: "var(--brand-destructive, #ba1a1a)" }}>
        Could not load the activity history. Please try again.
      </p>
    );
  }
  if (events.length === 0) {
    return (
      <p className="py-12 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }} data-testid="activity-empty">
        {emptyLabel ?? "No activity yet."}
      </p>
    );
  }

  return (
    <ol className="space-y-2" data-testid="activity-timeline">
      {events.map((e, i) => (
        <li
          key={`${e.action}-${e.occurredAt}-${i}`}
          data-testid="activity-row"
          data-action={e.action}
          className="flex items-start gap-3 rounded-xl p-4"
          style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "0 1px 3px rgba(0,13,34,0.06)" }}
        >
          <span
            className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: "var(--brand-viridian-xlight)", color: "var(--brand-viridian)" }}
          >
            <Activity className="w-5 h-5" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
              {humanizeEnumLabel(e.action)}
            </p>
            {(e.fromState || e.toState) && (
              <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
                {e.fromState ? `${e.fromState} → ` : ""}
                {e.toState ?? ""}
              </p>
            )}
            <p className="text-xs mt-1" style={{ color: "rgba(68,71,78,0.55)" }}>
              {new Date(e.occurredAt).toLocaleString()}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
