"use client";

import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Activity, CreditCard, Users, FileCheck, MessageSquare, AlertTriangle, FileText } from "lucide-react";
import { useNotifications } from "@components/shared/notifications/NotificationList";
import { notificationService, Notification } from "@components/shared/notifications/libs/notification-service";
import { ROUTES } from "@lib/routes";

const EVENT_ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  PAYMENT_CONFIRMED: CreditCard,
  AGENTS_ASSIGNED: Users,
  STATUS_CHANGE: Activity,
  REPORT_READY: FileCheck,
  NEW_MESSAGE: MessageSquare,
  SLA_BREACH: AlertTriangle,
  DISPUTE_RESOLVED: FileText,
  RECHECK_DECISION: FileText,
};

function entityRoute(n: Notification): string | null {
  if (n.entityType === "VERIFICATION" && n.entityId) {
    return ROUTES.PORTAL.VERIFICATION_DETAIL(n.entityId);
  }
  return null;
}

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function NotificationItem({ n, onRead }: { n: Notification; onRead: (id: string) => void }) {
  const router = useRouter();
  const Icon = EVENT_ICONS[n.eventType] ?? Bell;
  const route = entityRoute(n);

  function handleClick() {
    if (!n.read) onRead(n.id);
    if (route) router.push(route);
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="w-full flex items-start gap-4 px-6 py-4 text-left transition-colors hover:bg-gray-50"
      style={{
        borderBottom: "1px solid rgba(196,198,207,0.1)",
        backgroundColor: n.read ? "transparent" : "rgba(63,102,83,0.03)",
      }}
    >
      <div
        className="flex-shrink-0 w-9 h-9 rounded-full flex items-center justify-center"
        style={{ backgroundColor: n.read ? "rgba(0,13,34,0.05)" : "rgba(63,102,83,0.1)" }}
      >
        <Icon className="w-4 h-4" style={{ color: n.read ? "var(--brand-on-surface-variant)" : "var(--brand-viridian)" }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between gap-2">
          <p
            className="text-sm font-semibold leading-snug"
            style={{ color: "var(--brand-navy)", fontWeight: n.read ? 500 : 700 }}
          >
            {n.title}
          </p>
          <span className="text-xs flex-shrink-0 mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            {relativeTime(n.dateCreated)}
          </span>
        </div>
        <p className="text-xs mt-0.5 line-clamp-2" style={{ color: "var(--brand-on-surface-variant)" }}>
          {n.body}
        </p>
      </div>
      {!n.read && (
        <div className="flex-shrink-0 w-2 h-2 rounded-full mt-2" style={{ backgroundColor: "var(--brand-viridian)" }} />
      )}
    </button>
  );
}

export default function PortalNotificationsPage() {
  const qk = ["notifications"];
  const qc = useQueryClient();
  const { data, isLoading } = useNotifications();
  const notifications: Notification[] = (data as any)?.data ?? [];

  const markRead = useMutation({
    mutationFn: (id: string) => notificationService.markRead(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk }),
  });

  const markAllRead = useMutation({
    mutationFn: async () => {
      const unread = notifications.filter((n) => !n.read);
      await Promise.all(unread.map((n) => notificationService.markRead(n.id)));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: qk }),
  });

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
            Notifications
          </h1>
          {unreadCount > 0 && (
            <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
              {unreadCount} unread
            </p>
          )}
        </div>
        {unreadCount > 0 && (
          <button
            type="button"
            onClick={() => markAllRead.mutate()}
            disabled={markAllRead.isPending}
            className="text-xs font-medium px-3 py-1.5 rounded-lg border transition-opacity hover:opacity-70 disabled:opacity-40"
            style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-on-surface-variant)" }}
          >
            Mark all as read
          </button>
        )}
      </div>

      <div
        className="rounded-2xl overflow-hidden"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        {isLoading && (
          <div className="py-16 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            Loading…
          </div>
        )}

        {!isLoading && notifications.length === 0 && (
          <div className="py-20 text-center">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
            >
              <Bell className="w-6 h-6" style={{ color: "var(--brand-viridian)" }} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
              You&apos;re all caught up
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
              No notifications yet. We&apos;ll let you know when there&apos;s an update.
            </p>
          </div>
        )}

        {!isLoading && notifications.map((n) => (
          <NotificationItem
            key={n.id}
            n={n}
            onRead={(id) => markRead.mutate(id)}
          />
        ))}
      </div>
    </div>
  );
}
