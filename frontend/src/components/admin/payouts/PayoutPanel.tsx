"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, CheckCircle, PauseCircle, SlidersHorizontal } from "lucide-react";
import { payoutAdminService, Payout } from "@components/agents/payouts/libs/payout-service";
import { getErrorMessage } from "@lib/utils";
import { useState } from "react";
import AdjustPayoutModal from "./AdjustPayoutModal";

const adminPayoutQKey = ["admin", "payouts"];

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-700",
  APPROVED: "bg-blue-100 text-blue-700",
  PROCESSING: "bg-indigo-100 text-indigo-700",
  PAID: "bg-green-100 text-green-700",
  ON_HOLD: "bg-orange-100 text-orange-700",
};

export default function PayoutPanel() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: adminPayoutQKey,
    queryFn: () => payoutAdminService.listAll(),
  });
  const payouts: Payout[] = (data as any)?.data ?? [];
  const [error, setError] = useState<string | null>(null);
  const [adjusting, setAdjusting] = useState<Payout | null>(null);

  const approve = useMutation({
    mutationFn: (id: string) => payoutAdminService.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminPayoutQKey }),
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  const hold = useMutation({
    mutationFn: (id: string) =>
      payoutAdminService.hold(id, "Pending additional verification."),
    onSuccess: () => qc.invalidateQueries({ queryKey: adminPayoutQKey }),
    onError: (e: any) => setError(getErrorMessage(e)),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div data-testid="payout-panel">
      {adjusting && (
        <AdjustPayoutModal
          payoutId={adjusting.id}
          currentAmount={adjusting.amount}
          open={true}
          onClose={() => setAdjusting(null)}
        />
      )}

      {error && (
        <div className="mb-4 rounded bg-red-50 border border-red-200 px-4 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {payouts.length === 0 ? (
        <p className="text-center text-gray-500 py-10">No payout requests.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full text-sm bg-white">
            <thead className="border-b border-gray-200">
              <tr>
                {["Agent", "Amount", "Bank Account", "Requested", "Status", "Actions"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {payouts.map((p) => (
                <tr key={p.id} data-testid="payout-admin-row">
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{p.agentId.slice(0, 8)}…</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">₦{p.amount.toLocaleString()}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">{p.bankAccountId.slice(0, 8)}…</td>
                  <td className="px-4 py-3 text-gray-600">{new Date(p.requestedAt).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                        STATUS_STYLES[p.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {p.status}
                    </span>
                    {p.holdReason && (
                      <p className="text-xs text-orange-600 mt-0.5 max-w-[120px] truncate">{p.holdReason}</p>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {p.status === "PENDING" && (
                        <>
                          <button
                            type="button"
                            onClick={() => approve.mutate(p.id)}
                            disabled={approve.isPending}
                            style={{ cursor: "pointer" }}
                            title="Approve"
                            className="rounded p-1 text-green-600 hover:bg-green-50"
                            data-testid="payout-approve-button"
                          >
                            <CheckCircle className="h-4 w-4" />
                          </button>
                          <button
                            type="button"
                            onClick={() => hold.mutate(p.id)}
                            disabled={hold.isPending}
                            style={{ cursor: "pointer" }}
                            title="Put On Hold"
                            className="rounded p-1 text-orange-600 hover:bg-orange-50"
                            data-testid="payout-hold-button"
                          >
                            <PauseCircle className="h-4 w-4" />
                          </button>
                        </>
                      )}
                      {["PENDING", "APPROVED", "ON_HOLD"].includes(p.status) && (
                        <button
                          type="button"
                          onClick={() => setAdjusting(p)}
                          style={{ cursor: "pointer" }}
                          title="Adjust Amount"
                          className="rounded p-1 text-gray-500 hover:bg-gray-100"
                          data-testid="payout-adjust-button"
                        >
                          <SlidersHorizontal className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
