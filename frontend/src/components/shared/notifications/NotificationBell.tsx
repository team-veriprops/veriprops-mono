"use client";

import { Bell } from "lucide-react";

/**
 * Notification bell shown in the authenticated app shell. This is a
 * forward-compatible placeholder: it renders the affordance now and is wired to
 * live unread counts + a dropdown when the notification system lands (Phase 12).
 */
export default function NotificationBell({ dark = false }: { dark?: boolean }) {
  return (
    <button
      type="button"
      aria-label="Notifications"
      data-testid="notification-bell"
      className="relative w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 hover:bg-black/5"
      style={{ color: dark ? "rgba(255,255,255,0.8)" : "var(--brand-on-surface-variant)" }}
    >
      <Bell className="w-5 h-5" aria-hidden="true" />
    </button>
  );
}
