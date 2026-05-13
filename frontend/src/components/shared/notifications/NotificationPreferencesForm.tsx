"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notificationService, NotificationPreference } from "./libs/notification-service";

export type NotificationPersona = "customer" | "agent";

export const ALL_EVENTS = [
  { key: "STATUS_CHANGE", label: "Verification Status Change", personas: ["customer"] as string[] },
  { key: "PAYMENT_CONFIRMED", label: "Payment Confirmed", personas: ["customer"] as string[] },
  { key: "AGENTS_ASSIGNED", label: "Agents Assigned", personas: ["customer"] as string[] },
  { key: "JOB_ALERT", label: "New Job Alert", personas: ["agent"] as string[] },
  { key: "REPORT_READY", label: "Report Ready", personas: ["customer"] as string[] },
  { key: "NEW_MESSAGE", label: "New Message", personas: ["customer", "agent"] as string[] },
  { key: "REVISION_REQUEST", label: "Revision Requested", personas: ["agent"] as string[] },
  { key: "SLA_BREACH", label: "SLA Breach", personas: [] as string[] },
  { key: "RECHECK_DECISION", label: "Re-check Decision", personas: ["customer"] as string[] },
  { key: "DISPUTE_FILED", label: "Dispute Filed", personas: [] as string[] },
  { key: "DISPUTE_RESOLVED", label: "Dispute Resolved", personas: ["customer"] as string[] },
  { key: "PAYOUT_APPROVED", label: "Payout Approved", personas: ["agent"] as string[] },
  { key: "PAYOUT_HELD", label: "Payout On Hold", personas: ["agent"] as string[] },
];

export function getEventsForPersona(persona?: NotificationPersona) {
  return persona ? ALL_EVENTS.filter((e) => e.personas.includes(persona)) : ALL_EVENTS;
}

const CHANNELS: { key: keyof Omit<NotificationPreference, "userId" | "eventType">; label: string }[] = [
  { key: "emailEnabled", label: "Email" },
  { key: "smsEnabled", label: "SMS" },
  { key: "pushEnabled", label: "Push" },
];

interface Props {
  persona?: NotificationPersona;
}

export default function NotificationPreferencesForm({ persona }: Props) {
  const EVENTS = getEventsForPersona(persona);
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["notification-prefs"],
    queryFn: () => notificationService.getPreferences(),
  });

  const prefs: NotificationPreference[] = (data as any)?.data ?? [];

  const getPref = (eventType: string) =>
    prefs.find((p) => p.eventType === eventType) ?? {
      userId: "",
      eventType,
      emailEnabled: true,
      smsEnabled: false,
      pushEnabled: false,
    };

  const upsert = useMutation({
    mutationFn: (pref: Omit<NotificationPreference, "userId">) =>
      notificationService.upsertPreference(pref),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notification-prefs"] }),
  });

  const toggle = (eventType: string, channel: keyof Omit<NotificationPreference, "userId" | "eventType">) => {
    const current = getPref(eventType);
    upsert.mutate({ ...current, [channel]: !current[channel] });
  };

  if (isLoading) {
    return <div className="py-8 text-center text-sm text-gray-500">Loading preferences…</div>;
  }

  return (
    <div className="overflow-x-auto" data-testid="notification-preferences-form">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="py-3 pr-8 text-left font-medium text-gray-700">Event</th>
            {CHANNELS.map((ch) => (
              <th key={ch.key} className="px-4 py-3 text-center font-medium text-gray-700">
                {ch.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {EVENTS.map((ev) => {
            const pref = getPref(ev.key);
            return (
              <tr key={ev.key} data-testid={`pref-row-${ev.key}`}>
                <td className="py-3 pr-8 text-gray-800">{ev.label}</td>
                {CHANNELS.map((ch) => (
                  <td key={ch.key} className="px-4 py-3 text-center">
                    <button
                      type="button"
                      onClick={() => toggle(ev.key, ch.key)}
                      disabled={upsert.isPending}
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-1 ${
                        pref[ch.key] ? "bg-indigo-600" : "bg-gray-200"
                      }`}
                      aria-checked={pref[ch.key]}
                      aria-label={`${ev.label} ${ch.label}`}
                      data-testid={`pref-toggle-${ev.key}-${ch.key}`}
                    >
                      <span
                        className={`inline-block h-3 w-3 transform rounded-full bg-white shadow transition-transform ${
                          pref[ch.key] ? "translate-x-5" : "translate-x-1"
                        }`}
                      />
                    </button>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
