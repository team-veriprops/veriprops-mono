"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { earningsService, EarningRecord } from "./libs/earnings-service";

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-700",
  ON_HOLD: "bg-orange-100 text-orange-700",
  PAID: "bg-green-100 text-green-700",
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
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <p className="text-center text-sm text-gray-500 py-6">
        No earnings recorded yet. Complete tasks to start earning.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="job-breakdown-table">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-200">
            <th className="py-3 pr-4 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              Verification
            </th>
            <th className="py-3 pr-4 text-right text-xs font-medium uppercase tracking-wide text-gray-500">
              Gross
            </th>
            <th className="py-3 pr-4 text-right text-xs font-medium uppercase tracking-wide text-gray-500">
              Commission %
            </th>
            <th className="py-3 pr-4 text-right text-xs font-medium uppercase tracking-wide text-gray-500">
              Net
            </th>
            <th className="py-3 text-center text-xs font-medium uppercase tracking-wide text-gray-500">
              Status
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {records.map((r) => (
            <tr key={r.id} data-testid="job-earning-row">
              <td className="py-3 pr-4 font-mono text-xs text-gray-600">{r.verificationId.slice(0, 8)}…</td>
              <td className="py-3 pr-4 text-right text-gray-800">
                ₦{r.grossAmount.toLocaleString()}
              </td>
              <td className="py-3 pr-4 text-right text-gray-600">{r.commissionPct}%</td>
              <td className="py-3 pr-4 text-right font-semibold text-gray-900">
                ₦{r.netAmount.toLocaleString()}
              </td>
              <td className="py-3 text-center">
                <span
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    STATUS_STYLES[r.status] ?? "bg-gray-100 text-gray-600"
                  }`}
                >
                  {r.status}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
