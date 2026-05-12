"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { payoutService, Payout } from "./libs/payout-service";

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-blue-100 text-blue-700",
  PROCESSING: "bg-indigo-100 text-indigo-700",
  PAID: "bg-green-100 text-green-700",
  ON_HOLD: "bg-orange-100 text-orange-700",
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
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (payouts.length === 0) {
    return (
      <p className="text-center text-sm text-gray-500 py-6">
        No withdrawal requests yet.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="payout-history">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="py-3 pr-4 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              Amount
            </th>
            <th className="py-3 pr-4 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              Requested
            </th>
            <th className="py-3 pr-4 text-center text-xs font-medium uppercase tracking-wide text-gray-500">
              Status
            </th>
            <th className="py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              Note
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {payouts.map((p) => (
            <tr key={p.id} data-testid="payout-row">
              <td className="py-3 pr-4 font-semibold text-gray-900">
                ₦{p.amount.toLocaleString()}
              </td>
              <td className="py-3 pr-4 text-gray-600">
                {new Date(p.requestedAt).toLocaleDateString()}
              </td>
              <td className="py-3 pr-4 text-center">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    STATUS_STYLES[p.status] ?? "bg-gray-100 text-gray-600"
                  }`}
                >
                  {p.status}
                </span>
              </td>
              <td className="py-3 text-xs text-gray-500">
                {p.holdReason ?? (p.paidAt ? `Paid ${new Date(p.paidAt).toLocaleDateString()}` : "—")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
