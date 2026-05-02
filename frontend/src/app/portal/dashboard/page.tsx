"use client";

import Link from "next/link";
import { ArrowRight, ClipboardList, Plus } from "lucide-react";
import { useAuthStore } from "@components/website/auth/libs/useAuthStore";
import { useVerificationList } from "@components/portal/verifications/libs/useVerificationQueries";
import { Verification, VerificationStatus } from "@components/portal/verifications/libs/verification-service";
import { ROUTES } from "@lib/routes";

const STATUS_LABELS: Record<VerificationStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  PAYMENT_PENDING: "Payment Pending",
  PAID: "Paid",
  IN_PROGRESS: "In Progress",
  UNDER_REVIEW: "Under Review",
  COMPLETED: "Completed",
  DISPUTED: "Disputed",
  CANCELLED: "Cancelled",
  REFUNDED: "Refunded",
  FAILED: "Failed",
};

const STATUS_COLORS: Record<VerificationStatus, { bg: string; text: string }> = {
  DRAFT: { bg: "rgba(0,13,34,0.06)", text: "var(--brand-on-surface-variant)" },
  SUBMITTED: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6" },
  PAYMENT_PENDING: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
  PAID: { bg: "rgba(63,102,83,0.1)", text: "var(--brand-viridian)" },
  IN_PROGRESS: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6" },
  UNDER_REVIEW: { bg: "rgba(168,85,247,0.1)", text: "#9333ea" },
  COMPLETED: { bg: "rgba(63,102,83,0.15)", text: "var(--brand-viridian)" },
  DISPUTED: { bg: "rgba(239,68,68,0.1)", text: "#ef4444" },
  CANCELLED: { bg: "rgba(0,13,34,0.06)", text: "var(--brand-on-surface-variant)" },
  REFUNDED: { bg: "rgba(107,114,128,0.1)", text: "#6b7280" },
  FAILED: { bg: "rgba(239,68,68,0.1)", text: "#ef4444" },
};

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

function VerificationRow({ v }: { v: Verification }) {
  return (
    <Link
      href={ROUTES.PORTAL.VERIFICATION_DETAIL(v.id)}
      className="flex items-center gap-4 px-6 py-4 hover:bg-white transition-colors duration-150 group"
      style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-3 mb-1">
          <span className="text-sm font-mono font-semibold" style={{ color: "var(--brand-navy)" }}>
            {v.vid}
          </span>
          <StatusChip status={v.status} />
        </div>
        <div className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
          {v.tier} tier · {v.property?.state ?? "—"}{v.property?.lga ? `, ${v.property.lga}` : ""}
          {" · "}{new Date(v.createdAt).toLocaleDateString("en-NG", { day: "numeric", month: "short", year: "numeric" })}
        </div>
      </div>
      <ArrowRight
        className="w-4 h-4 flex-shrink-0 transition-transform group-hover:translate-x-0.5"
        style={{ color: "var(--brand-on-surface-variant)" }}
      />
    </Link>
  );
}

export default function PortalDashboardPage() {
  const session = useAuthStore((s) => s.session);
  const firstName = session?.user?.firstName ?? "there";
  const { data: verifications, isLoading } = useVerificationList();

  const hasVerifications = verifications && verifications.length > 0;

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      {/* Welcome heading */}
      <div className="mb-8">
        <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          Welcome back, {firstName}
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          Manage your property verifications below.
        </p>
      </div>

      {/* New verification CTA */}
      <div className="mb-8">
        <Link
          href={ROUTES.PORTAL.VERIFICATIONS_NEW}
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all duration-200 hover:opacity-90 hover:scale-[0.98] signature-gradient text-white"
          style={{ boxShadow: "0 4px 14px -3px rgba(0,13,34,0.3)" }}
        >
          <Plus className="w-4 h-4" />
          New Verification
        </Link>
      </div>

      {/* Verifications list */}
      <div
        className="rounded-2xl overflow-hidden"
        style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.15)", boxShadow: "0 2px 8px rgba(0,13,34,0.04)" }}
      >
        <div className="flex items-center gap-3 px-6 py-4" style={{ borderBottom: "1px solid rgba(196,198,207,0.12)" }}>
          <ClipboardList className="w-4 h-4" style={{ color: "var(--brand-viridian)" }} />
          <h2 className="text-sm font-bold" style={{ color: "var(--brand-navy)" }}>
            My Verifications
          </h2>
        </div>

        {isLoading && (
          <div className="px-6 py-10 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            Loading…
          </div>
        )}

        {!isLoading && !hasVerifications && (
          <div className="px-6 py-12 text-center">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
            >
              <ClipboardList className="w-6 h-6" style={{ color: "var(--brand-viridian)" }} />
            </div>
            <p className="text-sm font-medium mb-1" style={{ color: "var(--brand-navy)" }}>
              No verifications yet
            </p>
            <p className="text-xs mb-5" style={{ color: "var(--brand-on-surface-variant)" }}>
              Start your first property verification to protect your investment.
            </p>
            <Link
              href={ROUTES.PORTAL.VERIFICATIONS_NEW}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-bold transition-all duration-200 hover:opacity-90"
              style={{ backgroundColor: "rgba(63,102,83,0.08)", color: "var(--brand-viridian)", border: "1px solid rgba(63,102,83,0.2)" }}
            >
              <Plus className="w-3.5 h-3.5" />
              Verify a Property
            </Link>
          </div>
        )}

        {!isLoading && hasVerifications && verifications.map((v) => (
          <VerificationRow key={v.id} v={v} />
        ))}
      </div>
    </div>
  );
}
