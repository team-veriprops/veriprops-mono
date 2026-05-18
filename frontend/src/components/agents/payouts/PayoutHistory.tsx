"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { payoutService, Payout } from "./libs/payout-service";

const STATUS_COLORS: Record<string, { color: string; bg: string }> = {
  PENDING:    { color: "#d97706", bg: "rgba(245,158,11,0.1)" },
  APPROVED:   { color: "#2563eb", bg: "rgba(37,99,235,0.08)" },
  PROCESSING: { color: "#7c3aed", bg: "rgba(124,58,237,0.08)" },
  PAID:       { color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
  ON_HOLD:    { color: "#ea580c", bg: "rgba(234,88,12,0.1)" },
};

export const payoutQKey = ["agent", "payouts"];

export default function PayoutHistory() {
  const { data, isLoading } = useQuery({
    queryKey: payoutQKey,
    queryFn: () => payoutService.listPayouts(),
  });
  const payouts: Payout[] = (data as any)?.data ?? [];

  if (isLoading) {
    return (
      <div className="flex justify-center py-6">
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--brand-viridian)" }} />
      </div>
    );
  }

  if (payouts.length === 0) {
    return (
      <p className="text-center text-sm py-6" style={{ color: "var(--brand-on-surface-variant)" }}>
        No withdrawal requests yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="payout-history">
      <table className="min-w-full text-sm">
        <thead>
          <tr style={{ borderBottom: "1px solid rgba(196,198,207,0.2)" }}>
            {["Amount", "Requested", "Status", "Note"].map((h) => (
              <th
                key={h}
                className="py-3 pr-4 text-left text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--brand-on-surface-variant)" }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {payouts.map((p) => {
            const chip = STATUS_COLORS[p.status] ?? { color: "#6b7280", bg: "#f3f4f6" };
            return (
              <tr key={p.id} style={{ borderBottom: "1px solid rgba(196,198,207,0.1)" }} data-testid="payout-row">
                <td className="py-3 pr-4 font-semibold" style={{ color: "var(--brand-navy)" }}>
                  ₦{p.amount.toLocaleString()}
                </td>
                <td className="py-3 pr-4" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {new Date(p.requestedAt).toLocaleDateString()}
                </td>
                <td className="py-3 pr-4">
                  <span
                    className="rounded-full px-2.5 py-0.5 text-xs font-semibold"
                    style={{ color: chip.color, backgroundColor: chip.bg }}
                  >
                    {p.status}
                  </span>
                </td>
                <td className="py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {p.holdReason ?? (p.paidAt ? `Paid ${new Date(p.paidAt).toLocaleDateString()}` : "—")}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
