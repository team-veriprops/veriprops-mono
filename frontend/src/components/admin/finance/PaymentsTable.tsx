"use client";

import { useState } from "react";
import { CheckCircle, RefreshCw } from "lucide-react";
import {
  useAdminPayments,
  useConfirmWirePaymentMutation,
} from "@components/admin/libs/useAdminQueries";
import type { PaymentDto, PaymentStatus, PaymentMethod } from "@components/admin/libs/admin-service";

function statusBadge(status: PaymentStatus) {
  const map: Record<PaymentStatus, { label: string; color: string }> = {
    INITIATED: { label: "Initiated", color: "#6b7280" },
    PROCESSING: { label: "Processing", color: "#f59e0b" },
    SUCCEEDED: { label: "Succeeded", color: "#10b981" },
    FAILED: { label: "Failed", color: "#ef4444" },
    PENDING_TRANSFER: { label: "Pending Transfer", color: "#3b82f6" },
    PENDING_WIRE: { label: "Pending Wire", color: "#f59e0b" },
  };
  const s = map[status] ?? { label: status, color: "#6b7280" };
  return (
    <span
      className="px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ color: s.color, background: `${s.color}1A` }}
    >
      {s.label}
    </span>
  );
}

function formatMinor(minor: number, currency: string) {
  return `${currency} ${(minor / 100).toLocaleString("en-NG", { minimumFractionDigits: 2 })}`;
}

export default function PaymentsTable() {
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<PaymentStatus | "">("");
  const [methodFilter, setMethodFilter] = useState<PaymentMethod | "">("");

  const { data, isLoading, refetch } = useAdminPayments({
    status: statusFilter || undefined,
    method: methodFilter || undefined,
    page,
    pageSize: 25,
  });
  const confirmWire = useConfirmWirePaymentMutation();

  const payments = data?.items ?? [];
  const total = data?.meta?.total ?? 0;
  const pageCount = Math.ceil(total / 25);

  async function handleConfirmWire(paymentId: string) {
    await confirmWire.mutateAsync({ paymentId });
    refetch();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>
            Payments
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            {total} total payments
          </p>
        </div>
        <div className="flex gap-2 flex-wrap">
          <select
            className="px-3 py-2 rounded-lg text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value as PaymentStatus | ""); setPage(0); }}
          >
            <option value="">All statuses</option>
            <option value="PENDING_WIRE">Pending Wire</option>
            <option value="PENDING_TRANSFER">Pending Transfer</option>
            <option value="SUCCEEDED">Succeeded</option>
            <option value="FAILED">Failed</option>
          </select>
          <select
            className="px-3 py-2 rounded-lg text-sm border"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            value={methodFilter}
            onChange={(e) => { setMethodFilter(e.target.value as PaymentMethod | ""); setPage(0); }}
          >
            <option value="">All methods</option>
            <option value="CARD">Card</option>
            <option value="BANK_TRANSFER">Bank Transfer</option>
            <option value="WIRE">Wire</option>
          </select>
          <button
            type="button"
            className="p-2 rounded-lg border"
            style={{ borderColor: "rgba(196,198,207,0.4)" }}
            onClick={() => refetch()}
          >
            <RefreshCw className="w-4 h-4" style={{ color: "var(--brand-on-surface-variant)" }} />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>
      ) : payments.length === 0 ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No payments found.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid rgba(196,198,207,0.2)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "rgba(63,102,83,0.04)", borderBottom: "1px solid rgba(196,198,207,0.2)" }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>ID</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Verification</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Method</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Amount</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Status</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Date</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {payments.map((p: PaymentDto) => (
                <tr
                  key={p.id}
                  className="transition-colors"
                  style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}
                >
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {p.id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {p.verificationId.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--brand-navy)" }}>{p.method}</td>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--brand-navy)" }}>
                    {formatMinor(p.amountMinor, p.currency)}
                  </td>
                  <td className="px-4 py-3">{statusBadge(p.status)}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {new Date(p.dateCreated).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    {p.status === "PENDING_WIRE" && (
                      <button
                        type="button"
                        className="flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium text-white"
                        style={{ background: "var(--brand-viridian)" }}
                        onClick={() => handleConfirmWire(p.id)}
                        disabled={confirmWire.isPending}
                      >
                        <CheckCircle className="w-3.5 h-3.5" />
                        Confirm Wire
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
