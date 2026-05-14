"use client";

import { useState } from "react";
import { useAdminCommissions } from "@components/admin/libs/useAdminQueries";
import type { EarningDto, EarningStatus } from "@components/admin/libs/admin-service";

function statusBadge(status: EarningStatus) {
  const map: Record<EarningStatus, { label: string; color: string }> = {
    PENDING: { label: "Pending", color: "#f59e0b" },
    ON_HOLD: { label: "On Hold", color: "#6b7280" },
    PAID: { label: "Paid", color: "#10b981" },
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

export default function CommissionBreakdownTable() {
  const [page, setPage] = useState(0);
  const [statusFilter, setStatusFilter] = useState<EarningStatus | "">("");

  const { data, isLoading } = useAdminCommissions({
    status: statusFilter || undefined,
    page,
    pageSize: 25,
  });

  const items = data?.items ?? [];
  const total = data?.meta?.total ?? 0;
  const pageCount = Math.ceil(total / 25);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>
            Commission Breakdown
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            {total} total earnings records
          </p>
        </div>
        <select
          className="px-3 py-2 rounded-lg text-sm border"
          style={{ borderColor: "rgba(196,198,207,0.4)" }}
          value={statusFilter}
          onChange={(e) => { setStatusFilter(e.target.value as EarningStatus | ""); setPage(0); }}
        >
          <option value="">All statuses</option>
          <option value="PENDING">Pending</option>
          <option value="ON_HOLD">On Hold</option>
          <option value="PAID">Paid</option>
        </select>
      </div>

      {isLoading ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>
      ) : items.length === 0 ? (
        <div className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>No commission records found.</div>
      ) : (
        <div className="overflow-x-auto rounded-xl" style={{ border: "1px solid rgba(196,198,207,0.2)" }}>
          <table className="w-full text-sm">
            <thead>
              <tr style={{ background: "rgba(63,102,83,0.04)", borderBottom: "1px solid rgba(196,198,207,0.2)" }}>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Agent</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Gross</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Rate %</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Net</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Status</th>
                <th className="px-4 py-3 text-left font-medium" style={{ color: "var(--brand-on-surface-variant)" }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e: EarningDto) => (
                <tr
                  key={e.id}
                  className="transition-colors"
                  style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}
                >
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {e.agentId.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--brand-navy)" }}>
                    ₦{e.grossAmount.toLocaleString("en-NG")}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {e.commissionPct.toFixed(1)}%
                  </td>
                  <td className="px-4 py-3 font-medium" style={{ color: "var(--brand-viridian)" }}>
                    ₦{e.netAmount.toLocaleString("en-NG")}
                  </td>
                  <td className="px-4 py-3">{statusBadge(e.status)}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                    {new Date(e.dateCreated).toLocaleDateString()}
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
