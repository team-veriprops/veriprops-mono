"use client";

import { use } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  adminService,
  useSendBroadcastNowMutation,
  useCancelBroadcastMutation,
} from "@components/admin/libs/useAdminQueries";
import type { BroadcastStatus, PreviewBroadcastDto } from "@components/admin/libs/admin-service";
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
    <span className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ color, background: bg }}>
      {label}
    </span>
  );
}

export default function BroadcastDetailPage({ params }: { params: Promise<{ broadcastId: string }> }) {
  const { broadcastId } = use(params);

  const { data: previewData, isLoading } = useQuery({
    queryKey: ["admin", "broadcasts", broadcastId, "preview"],
    queryFn: () => adminService.previewBroadcast(broadcastId),
    staleTime: 60_000,
  });

  const sendNow = useSendBroadcastNowMutation();
  const cancel = useCancelBroadcastMutation();

  if (isLoading) {
    return (
      <div className="p-6 lg:p-8">
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
      </div>
    );
  }

  const preview = previewData?.data as PreviewBroadcastDto | undefined;

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Link href={ROUTES.ADMIN.BROADCASTS} className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
          ← Broadcasts
        </Link>
      </div>

      {preview ? (
        <div className="space-y-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h1 className="text-lg font-semibold" style={{ color: "var(--brand-navy)" }}>{preview.subject}</h1>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                  To: {preview.audience}
                </span>
                <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                  ~{preview.estimatedRecipients ?? 0} recipients
                </span>
              </div>
            </div>
          </div>

          <div
            className="rounded-xl p-5 text-sm whitespace-pre-wrap"
            style={{
              border: "1px solid rgba(196,198,207,0.3)",
              color: "var(--brand-navy)",
              background: "var(--brand-surface)",
            }}
          >
            {preview.bodyText}
          </div>

          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => sendNow.mutate(broadcastId)}
              disabled={sendNow.isPending}
              className="px-5 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
              style={{ background: "#10b981" }}
            >
              {sendNow.isPending ? "Sending…" : "Send Now"}
            </button>
            <button
              type="button"
              onClick={() => cancel.mutate(broadcastId)}
              disabled={cancel.isPending}
              className="px-5 py-2 rounded-lg text-sm font-medium border disabled:opacity-50"
              style={{ borderColor: "var(--destructive)", color: "var(--destructive)" }}
            >
              {cancel.isPending ? "Cancelling…" : "Cancel Broadcast"}
            </button>
          </div>
        </div>
      ) : (
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Broadcast not found.</p>
      )}
    </div>
  );
}
