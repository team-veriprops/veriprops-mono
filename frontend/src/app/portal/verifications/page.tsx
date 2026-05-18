"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Plus } from "lucide-react";
import { useVerificationList } from "@components/portal/verifications/libs/useVerificationQueries";
import { Verification, VerificationStatus } from "@components/portal/verifications/libs/verification-service";
import {
  STATUS_LABELS,
  STATUS_COLORS,
  ACTIVE_STATUSES,
  COMPLETED_STATUSES,
  CANCELLED_STATUSES,
} from "@components/portal/verifications/libs/status";
import { ROUTES } from "@lib/routes";

type Tab = "all" | "active" | "completed" | "cancelled";

const PAGE_SIZE = 100;

function StatusChip({ status }: { status: VerificationStatus }) {
  const { bg, text } = STATUS_COLORS[status] ?? STATUS_COLORS.DRAFT;
  return (
    <span
      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{ backgroundColor: bg, color: text }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function VerificationRow({ v, onClick }: { v: Verification; onClick: () => void }) {
  const location = [v.property?.state, v.property?.lga].filter(Boolean).join(", ") || "—";
  return (
    <tr
      className="hover:bg-gray-50 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-4 py-3 text-sm font-mono font-semibold" style={{ color: "var(--brand-navy)" }}>
        {v.vid}
      </td>
      <td className="px-4 py-3">
        <StatusChip status={v.status} />
      </td>
      <td className="px-4 py-3 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
        {v.tier}
      </td>
      <td className="px-4 py-3 text-sm truncate max-w-[200px]" style={{ color: "var(--brand-on-surface-variant)" }}>
        {location}
      </td>
      <td className="px-4 py-3 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
        {new Date(v.dateCreated).toLocaleDateString("en-NG", { day: "numeric", month: "short", year: "numeric" })}
      </td>
      <td className="px-4 py-3 text-right">
        <span className="text-xs font-medium" style={{ color: "var(--brand-viridian)" }}>
          View →
        </span>
      </td>
    </tr>
  );
}

function filterByTab(items: Verification[], tab: Tab): Verification[] {
  switch (tab) {
    case "active":
      return items.filter((v) => (ACTIVE_STATUSES as string[]).includes(v.status));
    case "completed":
      return items.filter((v) => (COMPLETED_STATUSES as string[]).includes(v.status));
    case "cancelled":
      return items.filter((v) => (CANCELLED_STATUSES as string[]).includes(v.status));
    default:
      return items;
  }
}

export default function PortalVerificationsPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("all");
  const [page, setPage] = useState(0);

  const { data, isLoading, isError } = useVerificationList(0, PAGE_SIZE);
  const allItems = data?.items ?? [];
  const filtered = filterByTab(allItems, tab);

  const PAGE_VIEW = 20;
  const totalPages = Math.ceil(filtered.length / PAGE_VIEW);
  const pagedItems = filtered.slice(page * PAGE_VIEW, (page + 1) * PAGE_VIEW);

  function handleTabChange(t: Tab) {
    setTab(t);
    setPage(0);
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "active", label: "Active" },
    { key: "completed", label: "Completed" },
    { key: "cancelled", label: "Cancelled" },
  ];

  return (
    <div className="p-6 lg:p-8 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          My Verifications
        </h1>
        <Link
          href={ROUTES.PORTAL.VERIFICATIONS_NEW}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all duration-200 hover:opacity-90 signature-gradient text-white"
          style={{ boxShadow: "0 4px 14px -3px rgba(0,13,34,0.3)" }}
        >
          <Plus className="w-4 h-4" />
          New Verification
        </Link>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 p-1 rounded-xl" style={{ backgroundColor: "rgba(0,13,34,0.04)" }}>
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => handleTabChange(key)}
            className="flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all duration-150"
            style={tab === key
              ? { backgroundColor: "#fff", color: "var(--brand-navy)", boxShadow: "0 1px 3px rgba(0,13,34,0.1)" }
              : { color: "var(--brand-on-surface-variant)" }}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        {isLoading && (
          <div className="py-16 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            Loading…
          </div>
        )}

        {isError && (
          <div className="py-16 text-center text-sm text-red-500">
            Failed to load verifications. Please try again.
          </div>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-sm font-medium mb-1" style={{ color: "var(--brand-navy)" }}>
              {tab === "all" ? "No verifications yet" : `No ${tab} verifications`}
            </p>
            {tab === "all" && (
              <p className="text-xs mb-5" style={{ color: "var(--brand-on-surface-variant)" }}>
                Start your first property verification to protect your investment.
              </p>
            )}
            {tab === "all" && (
              <Link
                href={ROUTES.PORTAL.VERIFICATIONS_NEW}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all duration-200 hover:opacity-90"
                style={{ backgroundColor: "rgba(63,102,83,0.08)", color: "var(--brand-viridian)", border: "1px solid rgba(63,102,83,0.2)" }}
              >
                <Plus className="w-3.5 h-3.5" />
                Verify a Property
              </Link>
            )}
          </div>
        )}

        {!isLoading && !isError && pagedItems.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(196,198,207,0.15)" }}>
                  {["VID", "Status", "Tier", "Location", "Started", ""].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-xs font-bold uppercase tracking-wider"
                      style={{ color: "var(--brand-on-surface-variant)" }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((v) => (
                  <VerificationRow
                    key={v.id}
                    v={v}
                    onClick={() => router.push(ROUTES.PORTAL.VERIFICATION_DETAIL(v.vid))}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ borderTop: "1px solid rgba(196,198,207,0.12)" }}
          >
            <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
              {page * PAGE_VIEW + 1}–{Math.min((page + 1) * PAGE_VIEW, filtered.length)} of {filtered.length}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-opacity disabled:opacity-40"
                style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)" }}
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-opacity disabled:opacity-40"
                style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)" }}
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
