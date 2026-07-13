"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Bell, CheckCheck } from "lucide-react";
import {
  useMarkAllReadMutation,
  useMarkNotificationReadMutation,
  useNotificationsQuery,
} from "./libs/useNotificationQueries";
import { cn } from "@lib/utils";

/** Full notification history (§N.4 "All notifications"). */
export default function NotificationsContainer() {
  const [page, setPage] = useState(0);
  const { data, isLoading } = useNotificationsQuery(page);
  const markRead = useMarkNotificationReadMutation();
  const markAll = useMarkAllReadMutation();
  const router = useRouter();

  const items = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div className="flex items-center justify-between mb-5">
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-brand-viridian" />
          <h1 className="text-xl font-semibold text-brand-navy">
            Notifications
          </h1>
        </div>
        <button
          onClick={() => markAll.mutate()}
          className="text-sm flex items-center gap-1.5 text-gray-500 hover:text-gray-700"
        >
          <CheckCheck className="w-4 h-4" /> Mark all read
        </button>
      </div>

      {isLoading && <p className="text-sm text-gray-400">Loading…</p>}
      {!isLoading && items.length === 0 && (
        <div className="text-center py-12 rounded-xl border border-black/5 bg-white">
          <Bell className="w-8 h-8 mx-auto text-gray-300 mb-2" />
          <p className="text-sm text-gray-500">No notifications yet.</p>
        </div>
      )}

      <ul className="space-y-2">
        {items.map((n) => (
          <li key={n.id}>
            <button
              onClick={() => {
                markRead.mutate(n.id);
                if (n.link) router.push(n.link);
              }}
              className={cn(
                "w-full text-left rounded-xl border border-black/5 bg-white px-4 py-3 hover:bg-black/[0.02]",
                !n.read && "bg-brand-viridian/4"
              )}
            >
              <div className="flex items-center gap-2">
                {!n.read && (
                  <span className="w-2 h-2 rounded-full shrink-0 bg-brand-viridian" />
                )}
                <p className="text-sm font-medium text-brand-navy">
                  {n.title}
                </p>
              </div>
              {n.body && <p className="text-xs text-gray-500 mt-1">{n.body}</p>}
            </button>
          </li>
        ))}
      </ul>

      {meta && meta.totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-5">
          <button
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="text-sm px-3 py-1.5 rounded-lg border border-black/10 disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-sm text-gray-400 py-1.5">
            {page + 1} / {meta.totalPages}
          </span>
          <button
            disabled={page + 1 >= meta.totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="text-sm px-3 py-1.5 rounded-lg border border-black/10 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
