"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { earningsService, EarningRecord } from "./libs/earnings-service";

const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  PENDING: { color: "#d97706", bg: "rgba(245,158,11,0.1)" },
  ON_HOLD: { color: "#ea580c", bg: "rgba(234,88,12,0.1)" },
  PAID:    { color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
};

export default function JobBreakdownTable() {
  const { data, isLoading } = useQuery({
    queryKey: ["agent", "earnings", "jobs"],
    queryFn: () => earningsService.listJobs(),
  });
  const records: EarningRecord[] = (data as any)?.data ?? [];

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--brand-viridian)" }} />
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <p className="text-center text-sm py-6" style={{ color: "var(--brand-on-surface-variant)" }}>
        No earnings recorded yet. Complete tasks to start earning.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="job-breakdown-table">
      <table className="min-w-full text-sm">
        <thead>
          <tr style={{ borderBottom: "1px solid rgba(196,198,207,0.2)" }}>
            {["Verification", "Gross", "Commission %", "Net", "Status"].map((h, i) => (
              <th
                key={h}
                className={`py-3 pr-4 text-xs font-semibold uppercase tracking-wide ${i >= 1 && i <= 3 ? "text-right" : i === 4 ? "text-center" : "text-left"}`}
                style={{ color: "var(--brand-on-surface-variant)" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {records.map((r) => {
            const chip = STATUS_COLORS[r.status] ?? { color: "#6b7280", bg: "#f3f4f6" };
            return (
              <tr key={r.id} style={{ borderBottom: "1px solid rgba(196,198,207,0.1)" }} data-testid="job-earning-row">
                <td className="py-3 pr-4 font-mono text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {r.verificationId.slice(0, 8)}…
                </td>
                <td className="py-3 pr-4 text-right" style={{ color: "var(--brand-navy)" }}>
                  ₦{r.grossAmount.toLocaleString()}
                </td>
                <td className="py-3 pr-4 text-right" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {r.commissionPct}%
                </td>
                <td className="py-3 pr-4 text-right font-semibold" style={{ color: "var(--brand-navy)" }}>
                  ₦{r.netAmount.toLocaleString()}
                </td>
                <td className="py-3 text-center">
                  <span
                    className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                    style={{ color: chip.color, backgroundColor: chip.bg }}
                  >
                    {r.status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
