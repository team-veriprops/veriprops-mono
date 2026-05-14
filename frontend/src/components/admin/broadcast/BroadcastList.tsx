"use client";

import { useState } from "react";
import { Send, X, Eye } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  useBroadcasts,
  useSendBroadcastNowMutation,
  useCancelBroadcastMutation,
} from "@components/admin/libs/useAdminQueries";
import type { BroadcastDto, BroadcastStatus } from "@components/admin/libs/admin-service";
import { ROUTES } from "@lib/routes";

function StatusBadge({ status }: { status: BroadcastStatus }) {
  const config: Record<BroadcastStatus, { label: string; color: string; bg: string }> = {
    DRAFT:     { label: "Draft",     color: "#f59e0b", bg: "#f59e0b1A" },
    SCHEDULED: { label: "Scheduled", color: "#3b82f6", bg: "#3b82f61A" },
    SENDING:   { label: "Sending",   color: "#8b5cf6", bg: "#8b5cf61A" },
    SENT:      { label: "Sent",      color: "#10b981", bg: "#10b9811A" },
    CANCELLED: { label: "Cancelled", color: "#6b7280", bg: "#6b72801A" },
  };
  const { label, color, bg } = config[status] ?? config.DRAFT;
  return (
    <span
      className="px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ color, background: bg }}
    >
      {label}
    </span>
  );
}

export default function BroadcastList() {
  const router = useRouter();
  const [page, setPage] = useState(0);
  const { data, isLoading } = useBroadcasts({ page });
  const sendNow = useSendBroadcastNowMutation();
  const cancel = useCancelBroadcastMutation();

  const items = data?.items ?? [];
  const total = data?.meta?.total ?? 0;
  const pageCount = Math.ceil(total / 25);

  const canSend = (b: BroadcastDto) => b.status === "DRAFT" || b.status === "SCHEDULED";
  const canCancel = (b: BroadcastDto) => b.status === "DRAFT" || b.status === "SCHEDULED";

  if (isLoading) {
    return <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>;
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No broadcasts yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid rgba(196,198,207,0.2)" }}>
        <table className="w-full text-sm">
          <thead>
            <tr style={{ background: "rgba(63,102,83,0.04)", borderBottom: "1px solid rgba(196,198,207,0.2)" }}>
              <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Subject</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Audience</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Status</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Recipients</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Created</th>
              <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {items.map((b: BroadcastDto) => (
              <tr key={b.id} style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}>
                <td className="px-4 py-3 font-medium" style={{ color: "var(--brand-navy)" }}>
                  {b.subject}
                  {b.scheduledAt && (
                    <span className="ml-2 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                      → {new Date(b.scheduledAt).toLocaleDateString()}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>{b.audience}</td>
                <td className="px-4 py-3"><StatusBadge status={b.status} /></td>
                <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {b.sentCount ?? 0}{b.totalRecipients ? ` / ${b.totalRecipients}` : ""}
                </td>
                <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {new Date(b.dateCreated).toLocaleDateString()}
                </td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="p-1.5 rounded-lg"
                      style={{ color: "var(--brand-viridian)" }}
                      onClick={() => router.push(ROUTES.ADMIN.BROADCAST_DETAIL(b.id))}
                      title="View"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    {canSend(b) && (
                      <button
                        type="button"
                        className="p-1.5 rounded-lg"
                        style={{ color: "#10b981" }}
                        onClick={() => sendNow.mutate(b.id)}
                        disabled={sendNow.isPending}
                        title="Send Now"
                      >
                        <Send className="w-4 h-4" />
                      </button>
                    )}
                    {canCancel(b) && (
                      <button
                        type="button"
                        className="p-1.5 rounded-lg"
                        style={{ color: "var(--destructive)" }}
                        onClick={() => cancel.mutate(b.id)}
                        disabled={cancel.isPending}
                        title="Cancel"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pageCount > 1 && (
        <div className="flex items-center gap-2 justify-end">
          <button
            type="button"
            className="px-3 py-1 rounded-lg text-sm border disabled:opacity-40"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
          >
            Previous
          </button>
          <span className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            {page + 1} / {pageCount}
          </span>
          <button
            type="button"
            className="px-3 py-1 rounded-lg text-sm border disabled:opacity-40"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            disabled={page >= pageCount - 1}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
