"use client";

import { useState } from "react";
import {
  useErasureRequests,
  useApproveErasureMutation,
  useRejectErasureMutation,
  useExecuteErasureMutation,
} from "@components/admin/libs/useAdminQueries";
import type { ErasureRequestDto, ErasureStatus } from "@components/admin/libs/admin-service";
import { Loader2 } from "lucide-react";

const STATUS_STYLES: Record<ErasureStatus, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-blue-100 text-blue-700",
  EXECUTED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
};

const FILTER_TABS: { label: string; value: ErasureStatus | undefined }[] = [
  { label: "All", value: undefined },
  { label: "Pending", value: "PENDING" },
  { label: "Approved", value: "APPROVED" },
  { label: "Executed", value: "EXECUTED" },
  { label: "Rejected", value: "REJECTED" },
];

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function ErasureRequestsPage() {
  const [statusFilter, setStatusFilter] = useState<ErasureStatus | undefined>(undefined);
  const [page, setPage] = useState(0);
  const [rejectModal, setRejectModal] = useState<{ id: string } | null>(null);
  const [rejectReason, setRejectReason] = useState("");

  const { data, isLoading, error } = useErasureRequests(statusFilter, page);
  const approve = useApproveErasureMutation();
  const reject = useRejectErasureMutation();
  const execute = useExecuteErasureMutation();

  const result = (data as any)?.data ?? null;

  const handleApprove = async (id: string) => {
    if (!confirm("Approve this erasure request?")) return;
    await approve.mutateAsync(id);
  };

  const handleExecute = async (id: string) => {
    if (!confirm("Execute erasure? This will permanently anonymise the user's PII. This cannot be undone.")) return;
    await execute.mutateAsync(id);
  };

  const handleReject = async () => {
    if (!rejectModal || !rejectReason.trim()) return;
    await reject.mutateAsync({ requestId: rejectModal.id, reason: rejectReason.trim() });
    setRejectModal(null);
    setRejectReason("");
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Data Erasure Requests</h1>

      {/* Status tabs */}
      <div className="flex gap-1 mb-6">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.label}
            onClick={() => { setStatusFilter(tab.value); setPage(0); }}
            style={{ cursor: "pointer" }}
            className={`text-sm px-3 py-1.5 rounded ${
              statusFilter === tab.value
                ? "bg-indigo-600 text-white"
                : "text-gray-600 hover:bg-gray-100"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      )}

      {error && <p className="text-sm text-red-600">Unable to load requests.</p>}

      {result && result.items.length === 0 && (
        <p className="text-sm text-gray-400 italic">No erasure requests found.</p>
      )}

      {result && result.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">User</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Requested</th>
                  <th className="px-4 py-2 text-left">Reason</th>
                  <th className="px-4 py-2 text-left">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.items.map((req: ErasureRequestDto) => (
                  <tr key={req.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-xs text-gray-600">
                      {req.userId.slice(0, 12)}…
                    </td>
                    <td className="px-4 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_STYLES[req.status]}`}>
                        {req.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500">
                      {formatDate(req.requestedAt)}
                    </td>
                    <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">
                      {req.reason ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {req.status === "PENDING" && (
                          <>
                            <button
                              onClick={() => handleApprove(req.id)}
                              disabled={approve.isPending}
                              style={{ cursor: "pointer" }}
                              className="text-xs text-blue-700 border border-blue-200 rounded px-2 py-1 hover:bg-blue-50 disabled:opacity-50"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => setRejectModal({ id: req.id })}
                              style={{ cursor: "pointer" }}
                              className="text-xs text-red-600 border border-red-200 rounded px-2 py-1 hover:bg-red-50"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {req.status === "APPROVED" && (
                          <button
                            onClick={() => handleExecute(req.id)}
                            disabled={execute.isPending}
                            style={{ cursor: "pointer" }}
                            className="text-xs text-red-700 border border-red-300 rounded px-2 py-1 hover:bg-red-50 disabled:opacity-50 font-medium"
                          >
                            Execute Erasure
                          </button>
                        )}
                        {req.status === "REJECTED" && req.rejectionReason && (
                          <span className="text-xs text-gray-500 italic">{req.rejectionReason}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.total > result.pageSize && (
            <div className="flex items-center justify-between mt-4 text-sm text-gray-500">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                style={{ cursor: page === 0 ? "default" : "pointer" }}
                className="disabled:opacity-40"
              >
                Previous
              </button>
              <span>
                Page {page + 1} of {Math.ceil(result.total / result.pageSize)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={(page + 1) * result.pageSize >= result.total}
                style={{ cursor: (page + 1) * result.pageSize >= result.total ? "default" : "pointer" }}
                className="disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </>
      )}

      {/* Reject modal */}
      {rejectModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 shadow-xl w-full max-w-sm">
            <h2 className="text-base font-semibold text-gray-900 mb-3">Reject Erasure Request</h2>
            <p className="text-sm text-gray-600 mb-3">
              Provide a reason that will be communicated to the user.
            </p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Rejection reason…"
              rows={3}
              className="w-full border border-gray-300 rounded px-3 py-2 text-sm resize-none mb-4"
            />
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => { setRejectModal(null); setRejectReason(""); }}
                style={{ cursor: "pointer" }}
                className="text-sm text-gray-500 px-3 py-1.5 hover:text-gray-700"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={!rejectReason.trim() || reject.isPending}
                style={{ cursor: !rejectReason.trim() || reject.isPending ? "default" : "pointer" }}
                className="text-sm bg-red-600 text-white px-4 py-1.5 rounded hover:bg-red-700 disabled:opacity-50"
              >
                {reject.isPending ? "Rejecting…" : "Reject"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
