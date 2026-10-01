"use client";

import { BellRing, Lock } from "lucide-react";
import {
  useNotificationPreferencesQuery,
  useSetPreferenceMutation,
} from "./libs/useNotificationQueries";
import { ChannelMode, type NotificationPreference } from "@/types/notification";
import { getErrorMessage } from "@lib/errors";

type Channel = "email" | "sms";

/**
 * Per-event email/SMS opt-out (§12.4). The backend lists the events this user may change, their
 * copy, and each channel's mode; this page renders exactly that. In-app delivery is always on.
 */
export default function NotificationPreferences() {
  const { data: prefs = [], isLoading, isError, error } = useNotificationPreferencesQuery();
  const set = useSetPreferenceMutation();

  function toggle(pref: NotificationPreference, channel: Channel, value: boolean) {
    set.mutate({
      eventType: pref.eventType,
      emailEnabled: channel === "email" ? value : pref.emailEnabled,
      smsEnabled: channel === "sms" ? value : pref.smsEnabled,
    });
  }

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="flex items-center gap-2 mb-1">
        <BellRing className="w-5 h-5 text-brand-viridian" />
        <h1 className="text-xl font-semibold text-brand-navy">
          Notification preferences
        </h1>
      </div>
      <p className="text-sm text-brand-on-surface-variant mb-5">
        Choose how you hear from us. In-app notifications are always on.
      </p>

      {isLoading ? (
        <p className="text-sm text-brand-on-surface-variant">Loading…</p>
      ) : isError ? (
        <p role="alert" className="text-sm text-danger">
          {getErrorMessage(error, "Could not load your notification preferences.")}
        </p>
      ) : prefs.length === 0 ? (
        <p className="text-sm text-brand-on-surface-variant">There are no email or SMS notifications to change on your account.</p>
      ) : (
        <div className="rounded-xl border border-black/5 bg-white overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-4 py-2.5 border-b border-black/5 text-xs font-semibold text-brand-on-surface-variant uppercase">
            <span>Event</span>
            <span className="w-12 text-center">Email</span>
            <span className="w-12 text-center">SMS</span>
          </div>
          {prefs.map((p) => (
            <div
              key={p.eventType}
              className="grid grid-cols-[1fr_auto_auto] gap-4 items-center px-4 py-3 border-b border-black/5 last:border-0"
            >
              <div>
                <p className="text-sm font-medium text-brand-navy">{p.label}</p>
                <p className="text-xs text-brand-on-surface-variant">{p.description}</p>
              </div>
              <ChannelCell pref={p} channel="email" mode={p.emailMode} enabled={p.emailEnabled} onToggle={toggle} />
              <ChannelCell pref={p} channel="sms" mode={p.smsMode} enabled={p.smsEnabled} onToggle={toggle} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ChannelCell({
  pref, channel, mode, enabled, onToggle,
}: {
  pref: NotificationPreference;
  channel: Channel;
  mode: ChannelMode;
  enabled: boolean;
  onToggle: (pref: NotificationPreference, channel: Channel, value: boolean) => void;
}) {
  const name = `${pref.label} ${channel === "email" ? "email" : "SMS"}`;
  if (mode === ChannelMode.OPTIONAL) {
    return (
      <input
        type="checkbox"
        className="w-12 justify-self-center"
        checked={enabled}
        onChange={(ev) => onToggle(pref, channel, ev.target.checked)}
        aria-label={name}
      />
    );
  }
  if (mode === ChannelMode.REQUIRED) {
    return (
      <span className="w-12 flex justify-center text-brand-on-surface-variant" title="Always sent" aria-label={`${name}: always sent`}>
        <Lock className="w-4 h-4" />
      </span>
    );
  }
  return (
    <span className="w-12 text-center text-brand-on-surface-variant" aria-label={`${name}: not used`}>
      —
    </span>
  );
}
