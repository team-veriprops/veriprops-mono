"use client";

import Link from "next/link";
import { AlertTriangle, Plus, X } from "lucide-react";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { useVerificationList, useCancelVerificationMutation } from "@components/portal/verifications/libs/useVerificationQueries";
import { Verification, VerificationStatus } from "@components/portal/verifications/libs/verification-service";
import { ACTIVE_STATUSES } from "@components/portal/verifications/libs/status";
import { useDashboardSummary } from "@components/portal/dashboard/useDashboardSummary";
import { AbandonedVerificationSummary } from "@components/portal/dashboard/dashboard-service";
import SummaryCounters from "@components/portal/dashboard/SummaryCounters";
import ActiveVerificationCard from "@components/portal/dashboard/ActiveVerificationCard";
import ReportsReadyAlert from "@components/portal/dashboard/ReportsReadyAlert";
import DashboardEmptyState from "@components/portal/dashboard/DashboardEmptyState";
import { ROUTES } from "@lib/routes";

const PAYMENT_PENDING_FIRST: VerificationStatus[] = ["PAYMENT_PENDING", "PAID", "IN_PROGRESS", "UNDER_REVIEW"];

function sortActiveFirst(items: Verification[]): Verification[] {
  return [...items].sort((a, b) => {
    const ai = PAYMENT_PENDING_FIRST.indexOf(a.status);
    const bi = PAYMENT_PENDING_FIRST.indexOf(b.status);
    if (ai !== bi) return ai - bi;
    return new Date(b.dateCreated).getTime() - new Date(a.dateCreated).getTime();
  });
}

function BackendAbandonmentBanner({
  v,
  onDiscard,
}: {
  v: AbandonedVerificationSummary;
  onDiscard: (id: string) => void;
}) {
  const address = v.propertyAddress ?? v.propertyState ?? "Unknown property";
  return (
    <div
      className="flex items-start gap-3 p-4 rounded-xl"
      style={{ backgroundColor: "rgba(245,158,11,0.07)", border: "1px solid rgba(245,158,11,0.2)" }}
    >
      <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" style={{ color: "#d97706" }} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
          Incomplete verification
        </p>
        <p className="text-xs mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          {address} · {v.tier} tier
          {v.totalAmountMinor != null && (
            <span> · ₦{(v.totalAmountMinor / 100).toLocaleString("en-NG")}</span>
          )}
        </p>
        <div className="flex items-center gap-2 mt-2">
          <Link
            href={ROUTES.PORTAL.VERIFICATION_DETAIL(v.vid)}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-bold text-white"
            style={{ backgroundColor: "var(--brand-viridian)" }}
          >
            Continue
          </Link>
          <button
            type="button"
            onClick={() => onDiscard(v.id)}
            className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border"
            style={{ color: "var(--brand-on-surface-variant)", borderColor: "rgba(196,198,207,0.4)" }}
          >
            <X className="w-3 h-3" />
            Discard
          </button>
        </div>
      </div>
    </div>
  );
}

export default function PortalDashboardPage() {
  const session = useAuthStore((s) => s.session);
  const firstName = session?.user?.firstName ?? "there";

  const { data: summary, isLoading: summaryLoading } = useDashboardSummary();
  const { data: verifications, isLoading: verLoading } = useVerificationList();
  const cancelMutation = useCancelVerificationMutation();

  const isLoading = summaryLoading || verLoading;
  const total = summary?.total ?? 0;

  const allItems = verifications?.items ?? [];
  const activeItems = allItems.filter((v) => (ACTIVE_STATUSES as string[]).includes(v.status));
  const sortedActive = sortActiveFirst(activeItems);
  const visibleActive = sortedActive.slice(0, 3);
  const hasMoreActive = sortedActive.length > 3;

  const abandoned = summary?.abandoned ?? [];

  async function handleDiscard(id: string) {
    await cancelMutation.mutateAsync(id);
  }

  return (
    <div className="p-6 lg:p-8 max-w-3xl mx-auto">
      {/* Abandonment banners — sourced from backend */}
      {abandoned.length > 0 && (
        <div className="mb-6 space-y-3">
          {abandoned.map((v) => (
            <BackendAbandonmentBanner key={v.id} v={v} onDiscard={handleDiscard} />
          ))}
        </div>
      )}

      {/* Header row */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
            Welcome back, {firstName}
          </h1>
        </div>
        {total > 0 && (
          <Link
            href={ROUTES.PORTAL.VERIFICATIONS_NEW}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-bold transition-all duration-200 hover:opacity-90"
            style={{ backgroundColor: "rgba(63,102,83,0.08)", color: "var(--brand-viridian)", border: "1px solid rgba(63,102,83,0.2)" }}
          >
            <Plus className="w-4 h-4" />
            New
          </Link>
        )}
      </div>

      {/* Reports ready alert */}
      {(summary?.unreadReportCount ?? 0) > 0 && (
        <ReportsReadyAlert count={summary!.unreadReportCount} />
      )}

      {/* Summary counters */}
      {!isLoading && total > 0 && (
        <SummaryCounters
          total={summary?.total ?? 0}
          active={summary?.active ?? 0}
          completed={summary?.completed ?? 0}
        />
      )}

      {/* Empty state */}
      {!isLoading && total === 0 && <DashboardEmptyState />}

      {/* Active verifications */}
      {total > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-bold" style={{ color: "var(--brand-navy)" }}>
              Active Verifications
            </h2>
            {hasMoreActive && (
              <Link
                href={ROUTES.PORTAL.VERIFICATIONS}
                className="text-xs font-medium transition-opacity hover:opacity-70"
                style={{ color: "var(--brand-viridian)" }}
              >
                View all →
              </Link>
            )}
          </div>

          {verLoading && (
            <div className="py-8 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
              Loading…
            </div>
          )}

          {!verLoading && visibleActive.length === 0 && (
            <p className="text-sm py-4" style={{ color: "var(--brand-on-surface-variant)" }}>
              No active verifications right now.{" "}
              <Link href={ROUTES.PORTAL.VERIFICATIONS} style={{ color: "var(--brand-viridian)", fontWeight: 600 }}>
                View all →
              </Link>
            </p>
          )}

          {!verLoading && visibleActive.length > 0 && (
            <div className="space-y-3">
              {visibleActive.map((v) => (
                <ActiveVerificationCard key={v.id} verification={v} />
              ))}
              {hasMoreActive && (
                <Link
                  href={ROUTES.PORTAL.VERIFICATIONS}
                  className="block text-center py-3 rounded-xl text-xs font-semibold transition-colors hover:opacity-80"
                  style={{ color: "var(--brand-viridian)", backgroundColor: "rgba(63,102,83,0.05)", border: "1px dashed rgba(63,102,83,0.2)" }}
                >
                  + {sortedActive.length - 3} more active verifications
                </Link>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
