"use client";

import { useMemo } from "react";
import { BellRing } from "lucide-react";
import {
  useNotificationPreferencesQuery,
  useSetPreferenceMutation,
} from "./libs/useNotificationQueries";

// Backend event types a user can opt out of by channel (§12.4). In-app can't be disabled.
const EVENTS: { type: string; label: string; description: string }[] = [
  { type: "PAYMENT_CONFIRMED", label: "Payment confirmed", description: "When your payment is received." },
  { type: "STATUS_CHANGED", label: "Status updates", description: "When your verification advances a stage." },
  { type: "AGENTS_ASSIGNED", label: "Agents assigned", description: "When our agents start work." },
  { type: "REPORT_READY", label: "Report ready", description: "When your report is available." },
  { type: "SLA_BREACHED", label: "Delays", description: "If a verification runs past its target date." },
  { type: "NEW_JOB", label: "New jobs (agents)", description: "When a task is available for you." },
  { type: "TASK_REJECTED", label: "Revision requests (agents)", description: "When an admin requests a revision." },
];

/**
 * Per-event email/SMS opt-out (§12.4). Absence of a stored override means the platform
 * default (on) applies; toggling records the override. In-app delivery is always on.
 */
export default function NotificationPreferences() {
  const { data: prefs = [], isLoading } = useNotificationPreferencesQuery();
  const set = useSetPreferenceMutation();

  const byType = useMemo(() => {
    const map: Record<string, { emailEnabled: boolean; smsEnabled: boolean }> = {};
    for (const p of prefs) map[p.eventType] = { emailEnabled: p.emailEnabled, smsEnabled: p.smsEnabled };
    return map;
  }, [prefs]);

  function current(type: string) {
    return byType[type] ?? { emailEnabled: true, smsEnabled: true };
  }

  function toggle(type: string, channel: "email" | "sms", value: boolean) {
    const c = current(type);
    set.mutate({
      eventType: type,
      emailEnabled: channel === "email" ? value : c.emailEnabled,
      smsEnabled: channel === "sms" ? value : c.smsEnabled,
    });
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="flex items-center gap-2 mb-1">
        <BellRing className="w-5 h-5" style={{ color: "var(--brand-viridian)" }} />
        <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>
          Notification preferences
        </h1>
      </div>
      <p className="text-sm text-gray-500 mb-5">
        Choose how you hear from us. In-app notifications are always on.
      </p>

      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <div className="rounded-xl border border-black/5 bg-white overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-2.5 border-b border-black/5 text-xs font-semibold text-gray-400 uppercase">
            <span>Event</span>
            <span className="w-12 text-center">Email</span>
            <span className="w-12 text-center">SMS</span>
          </div>
          {EVENTS.map((e) => {
            const c = current(e.type);
            return (
              <div
                key={e.type}
                className="grid grid-cols-[1fr_auto_auto] gap-4 items-center px-4 py-3 border-b border-black/5 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
                    {e.label}
                  </p>
                  <p className="text-xs text-gray-400">{e.description}</p>
                </div>
                <input
                  type="checkbox"
                  className="w-12 justify-self-center"
                  checked={c.emailEnabled}
                  onChange={(ev) => toggle(e.type, "email", ev.target.checked)}
                  aria-label={`${e.label} email`}
                />
                <input
                  type="checkbox"
                  className="w-12 justify-self-center"
                  checked={c.smsEnabled}
                  onChange={(ev) => toggle(e.type, "sms", ev.target.checked)}
                  aria-label={`${e.label} sms`}
                />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
