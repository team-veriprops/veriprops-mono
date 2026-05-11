"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAdminVerifications } from "../libs/useAdminQueries";
import VerificationStatusBadge from "./VerificationStatusBadge";
import type { VerificationStatus, VerificationTier } from "../libs/admin-service";
import { ROUTES } from "@/lib/routes";

const STATUS_FILTERS: Array<{ label: string; value: VerificationStatus | "" }> = [
  { label: "All", value: "" },
  { label: "Paid", value: "PAID" },
  { label: "In Progress", value: "IN_PROGRESS" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Completed", value: "COMPLETED" },
  { label: "Paused", value: "PAUSED" },
  { label: "Cancelled", value: "CANCELLED" },
];

const TIER_FILTERS: Array<{ label: string; value: VerificationTier | "" }> = [
  { label: "All Tiers", value: "" },
  { label: "Basic", value: "BASIC" },
  { label: "Standard", value: "STANDARD" },
  { label: "Premium", value: "PREMIUM" },
];

export default function VerificationQueue() {
  const router = useRouter();
  const [status, setStatus] = useState<string>("");
  const [tier, setTier] = useState<string>("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useAdminVerifications({
    status: status || undefined,
    tier: tier || undefined,
    page,
  });

  const items = data?.items ?? [];
  const meta = data?.meta;

  return (
    <div className="space-y-4">
      {/* Filter chips */}
      <div className="flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => { setStatus(f.value); setPage(1); }}
            style={{ cursor: "pointer" }}
            className={`px-3 py-1 rounded-full text-sm border transition-colors ${
              status === f.value
                ? "bg-indigo-600 text-white border-indigo-600"
                : "bg-white text-gray-600 border-gray-300 hover:border-indigo-400"
            }`}
          >
            {f.label}
          </button>
        ))}
        <div className="h-4 border-l border-gray-300 mx-1" />
        {TIER_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => { setTier(f.value); setPage(1); }}
            style={{ cursor: "pointer" }}
            className={`px-3 py-1 rounded-full text-sm border transition-colors ${
              tier === f.value
                ? "bg-violet-600 text-white border-violet-600"
                : "bg-white text-gray-600 border-gray-300 hover:border-violet-400"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-12 text-center text-gray-500">Loading verifications…</div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-gray-500">No verifications found.</div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                {["VID", "Tier", "Status", "State/LGA", "Paid At", "Actions"].map((h) => (
                  <th
                    key={h}
                    className="px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wider text-xs"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-100">
              {items.map((v) => (
                <tr
                  key={v.id}
                  className="hover:bg-gray-50 transition-colors"
                  style={{ cursor: "pointer" }}
                  onClick={() => router.push(ROUTES.ADMIN.VERIFICATION_DETAIL(v.vid))}
                >
                  <td className="px-4 py-3 font-mono font-medium text-gray-900">{v.vid}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded bg-gray-100 text-gray-700 text-xs font-medium">
                      {v.tier}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <VerificationStatusBadge status={v.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {v.state ? `${v.state}${v.lga ? ` / ${v.lga}` : ""}` : "—"}
                  </td>
                  <td className="px-4 py-3 text-gray-500">
                    {v.paidAt ? new Date(v.paidAt).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        router.push(ROUTES.ADMIN.VERIFICATION_DETAIL(v.vid));
                      }}
                      style={{ cursor: "pointer" }}
                      className="text-indigo-600 hover:text-indigo-800 text-xs font-medium"
                    >
                      View →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {meta && meta.total > meta.pageSize && (
        <div className="flex items-center justify-between pt-2">
          <span className="text-sm text-gray-500">
            {meta.total} total · page {meta.page}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              style={{ cursor: page <= 1 ? "not-allowed" : "pointer" }}
              className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            >
              Prev
            </button>
            <button
              disabled={items.length < meta.pageSize}
              onClick={() => setPage((p) => p + 1)}
              style={{ cursor: items.length < meta.pageSize ? "not-allowed" : "pointer" }}
              className="px-3 py-1 border rounded text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
