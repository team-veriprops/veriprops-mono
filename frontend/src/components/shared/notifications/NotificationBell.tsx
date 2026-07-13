"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, CheckCheck } from "lucide-react";
import { ROUTES } from "@lib/routes";
import { cn } from "@lib/utils";
import {
  useMarkAllReadMutation,
  useMarkNotificationReadMutation,
  useNotificationRealtime,
  useNotificationUnreadQuery,
  useNotificationsQuery,
} from "@components/notifications/libs/useNotificationQueries";

/**
 * Notifications entry in the top nav (PRD §N.4). Shows a counter of new notifications
 * (numeric, "9+" cap, hidden at zero) and opens a dropdown with recent items + "View all".
 * The feed contains system updates only — routine chat messages never appear here (FR-6).
 */
export default function NotificationBell({ dark = false }: { dark?: boolean }) {
  useNotificationRealtime();
  const { data: count = 0 } = useNotificationUnreadQuery();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);
  const router = useRouter();
  const { data } = useNotificationsQuery(0, open);
  const markRead = useMarkNotificationReadMutation();
  const markAll = useMarkAllReadMutation();

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);

  const items = data?.items ?? [];

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        aria-label="Notifications"
        data-testid="notification-bell"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "relative w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 hover:bg-black/5",
          dark ? "text-white/80" : "text-brand-on-surface-variant"
        )}
      >
        <Bell className="w-5 h-5" aria-hidden="true" />
        {count > 0 && (
          <span
            data-testid="notification-unread-badge"
            className="absolute -top-0.5 -right-0.5 min-w-4 h-4 px-1 rounded-full text-[10px] font-bold text-white flex items-center justify-center bg-red-600"
          >
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div
          className="absolute right-0 mt-2 w-80 max-w-[90vw] rounded-xl border border-black/10 bg-white shadow-lg z-50 overflow-hidden"
          data-testid="notification-dropdown"
        >
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-black/5">
            <span className="text-sm font-semibold text-brand-navy">
              Notifications
            </span>
            {count > 0 && (
              <button
                onClick={() => markAll.mutate()}
                className="text-xs flex items-center gap-1 text-gray-500 hover:text-gray-700"
              >
                <CheckCheck className="w-3.5 h-3.5" /> Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 ? (
              <p className="text-sm text-gray-400 text-center py-8">No notifications yet.</p>
            ) : (
              items.map((n) => (
                <button
                  key={n.id}
                  onClick={() => {
                    markRead.mutate(n.id);
                    setOpen(false);
                    if (n.link) router.push(n.link);
                  }}
                  className={cn(
                    "w-full text-left px-4 py-2.5 hover:bg-black/2 border-b border-black/5 last:border-0",
                    !n.read && "bg-brand-viridian/4"
                  )}
                >
                  <p className="text-sm font-medium text-brand-navy">
                    {n.title}
                  </p>
                  {n.body && <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">{n.body}</p>}
                </button>
              ))
            )}
          </div>

          <Link
            href={ROUTES.PORTAL.NOTIFICATIONS}
            onClick={() => setOpen(false)}
            className="block text-center text-sm py-2.5 border-t border-black/5 hover:bg-black/2 text-brand-viridian"
          >
            View all
          </Link>
        </div>
      )}
    </div>
  );
}
