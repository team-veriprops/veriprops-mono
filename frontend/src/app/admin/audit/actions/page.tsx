"use client";

import { useState } from "react";
import { useAuditActions } from "@components/admin/libs/useAdminQueries";
import type { AuditPackRowDto } from "@components/admin/libs/admin-service";
import { Loader2, Search } from "lucide-react";

const ADMIN_ACTION_TYPES = [
  "ADMIN_INVITED",
  "ADMIN_INVITE_ACCEPTED",
  "ADMIN_ROLE_CHANGED",
  "ADMIN_CONFIG_CHANGED",
  "AGENT_APPROVED",
  "AGENT_REJECTED",
  "VERIFICATION_CANCELLED",
  "PAYOUT_APPROVED",
  "PAYOUT_REJECTED",
  "REPORT_RELEASED",
];

function formatDate(iso: string) {
  return new Date(iso).toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function AuditActionsPage() {
  const [page, setPage] = useState(0);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);

  const { data, isLoading, error } = useAuditActions({
    actionTypes: selectedTypes.length ? selectedTypes : undefined,
    dateFrom: dateFrom || undefined,
    dateTo: dateTo || undefined,
    page,
    pageSize: 20,
  });

  const result = (data as any)?.data ?? null;

  const toggleType = (type: string) =>
    setSelectedTypes((prev) =>
      prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
    );

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-6">Admin Action Log</h1>

      {/* Filters */}
      <div className="bg-gray-50 rounded-lg border border-gray-200 p-4 mb-6 space-y-3">
        <div className="flex gap-3 flex-wrap">
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(0); }}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs text-gray-500 font-medium">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(0); }}
              className="border border-gray-300 rounded px-2 py-1 text-sm"
            />
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500 font-medium mb-1.5">Action types</p>
          <div className="flex flex-wrap gap-1.5">
            {ADMIN_ACTION_TYPES.map((type) => (
              <button
                key={type}
                onClick={() => { toggleType(type); setPage(0); }}
                style={{ cursor: "pointer" }}
                className={`text-xs px-2 py-0.5 rounded border ${
                  selectedTypes.includes(type)
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-gray-400"
                }`}
              >
                {type.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-500" />
        </div>
      )}

      {error && (
        <p className="text-sm text-red-600">Unable to load audit log.</p>
      )}

      {result && result.items.length === 0 && (
        <p className="text-sm text-gray-400 italic">No actions found for the selected filters.</p>
      )}

      {result && result.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="min-w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">Time</th>
                  <th className="px-4 py-2 text-left">Action</th>
                  <th className="px-4 py-2 text-left">Resource</th>
                  <th className="px-4 py-2 text-left">State change</th>
                  <th className="px-4 py-2 text-left">Actor</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {result.items.map((row: AuditPackRowDto) => (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2 text-gray-500 whitespace-nowrap">
                      {formatDate(row.occurredAt)}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-800">
                      {row.action}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      <span className="font-medium">{row.resourceType}</span>
                      <br />
                      <span className="font-mono">{row.resourceId.slice(0, 12)}…</span>
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-500">
                      {row.fromState || row.toState ? (
                        <>
                          {row.fromState && (
                            <span className="text-gray-400">{row.fromState}</span>
                          )}
                          {row.fromState && row.toState && " → "}
                          {row.toState && (
                            <span className="text-gray-700 font-medium">{row.toState}</span>
                          )}
                        </>
                      ) : "—"}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs text-gray-500">
                      {row.actorId ? row.actorId.slice(0, 8) + "…" : "—"}
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
    </div>
  );
}
