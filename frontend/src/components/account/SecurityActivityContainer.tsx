"use client";

import { ShieldCheck, ShieldAlert, Activity, Mail, Loader2, Smartphone } from "lucide-react";
import AccountShell from "./AccountShell";
import { useSecurityEventsQuery } from "@components/website/auth/libs/useAuthQueries";
import { SecurityEvent, SecurityEventType } from "@components/website/auth/models";
import { formatDistanceToNow } from "date-fns";

const ICONS: Record<SecurityEventType, React.ComponentType<{ className?: string }>> = {
  [SecurityEventType.LOGIN_SUCCESS]:           ShieldCheck,
  [SecurityEventType.LOGIN_FAILURE]:           ShieldAlert,
  [SecurityEventType.OTP_SENT]:                Mail,
  [SecurityEventType.OTP_FAILURE]:             ShieldAlert,
  [SecurityEventType.PASSWORD_CHANGED]:        ShieldCheck,
  [SecurityEventType.PASSWORD_RESET_REQUESTED]:Mail,
  [SecurityEventType.ACCOUNT_LOCKED]:          ShieldAlert,
  [SecurityEventType.SESSION_REVOKED]:         Activity,
  [SecurityEventType.OAUTH_LINKED]:            ShieldCheck,
  [SecurityEventType.OAUTH_UNLINKED]:          Activity,
};

const TONES: Record<SecurityEventType, "ok" | "warn" | "info"> = {
  [SecurityEventType.LOGIN_SUCCESS]:           "ok",
  [SecurityEventType.LOGIN_FAILURE]:           "warn",
  [SecurityEventType.OTP_SENT]:                "info",
  [SecurityEventType.OTP_FAILURE]:             "warn",
  [SecurityEventType.PASSWORD_CHANGED]:        "ok",
  [SecurityEventType.PASSWORD_RESET_REQUESTED]:"info",
  [SecurityEventType.ACCOUNT_LOCKED]:          "warn",
  [SecurityEventType.SESSION_REVOKED]:         "info",
  [SecurityEventType.OAUTH_LINKED]:            "ok",
  [SecurityEventType.OAUTH_UNLINKED]:          "info",
};

const TONE_COLOR: Record<"ok" | "warn" | "info", string> = {
  ok:   "var(--brand-viridian)",
  warn: "var(--danger)",
  info: "var(--info)",
};

export default function SecurityActivityContainer() {
  const eventsQuery = useSecurityEventsQuery();
  const events = eventsQuery.data ?? [];

  return (
    <AccountShell
      title="Security activity"
      subtitle="Every sign-in, OTP, and password change on your account. Review regularly — anything suspicious should be reported immediately."
    >
      {eventsQuery.isLoading ? (
        <Loading />
      ) : events.length === 0 ? (
        <EmptyState />
      ) : (
        <ol className="space-y-3">
          {events.map((event) => (
            <EventRow key={event.id} event={event} />
          ))}
        </ol>
      )}
    </AccountShell>
  );
}

function Loading() {
  return (
    <div className="flex items-center justify-center py-16">
      <Loader2 className="w-6 h-6 animate-spin" style={{ color: "var(--brand-viridian)" }} />
    </div>
  );
}

function EmptyState() {
  return (
    <div
      className="rounded-xl p-10 text-center"
      style={{
        backgroundColor: "var(--brand-surface-card)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <ShieldCheck
        className="w-10 h-10 mx-auto mb-4"
        style={{ color: "var(--brand-viridian)" }}
      />
      <p className="text-base font-semibold" style={{ color: "var(--brand-navy)" }}>
        Nothing to show yet
      </p>
      <p className="text-sm mt-1.5" style={{ color: "var(--brand-on-surface-variant)" }}>
        Your security events will appear here as you use Veriprops.
      </p>
    </div>
  );
}

function EventRow({ event }: { event: SecurityEvent }) {
  const Icon = ICONS[event.type] ?? Activity;
  const tone = TONES[event.type] ?? "info";
  return (
    <li
      className="flex items-start gap-4 p-4 rounded-xl transition-colors hover:bg-[var(--brand-surface-low)]"
      style={{
        backgroundColor: "var(--brand-surface-card)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <span
        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
        style={{
          backgroundColor: `color-mix(in oklab, ${TONE_COLOR[tone]} 12%, transparent)`,
          color: TONE_COLOR[tone],
        }}
      >
        <Icon className="w-5 h-5" />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
          {event.description}
        </p>
        <div
          className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs"
          style={{ color: "var(--brand-on-surface-variant)" }}
        >
          <span>{formatRelative(event.occurredAt)}</span>
          {event.approxLocation && <span>· {event.approxLocation}</span>}
          {event.ipAddress && <span>· IP {event.ipAddress}</span>}
          {event.device && (
            <span className="inline-flex items-center gap-1">
              <Smartphone className="w-3 h-3" /> {event.device}
            </span>
          )}
        </div>
      </div>
    </li>
  );
}

function formatRelative(iso: string): string {
  try {
    return formatDistanceToNow(new Date(iso), { addSuffix: true });
  } catch {
    return iso;
  }
}
