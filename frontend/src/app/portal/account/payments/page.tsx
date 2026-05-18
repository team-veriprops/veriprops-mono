"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { CreditCard } from "lucide-react";
import { useMyPayments } from "@components/portal/verifications/libs/useVerificationQueries";
import { CustomerPayment, PaymentStatus } from "@components/portal/verifications/libs/payment-service";
import { ROUTES } from "@lib/routes";

const STATUS_LABELS: Record<PaymentStatus, string> = {
  INITIATED: "Initiated",
  PROCESSING: "Processing",
  SUCCEEDED: "Succeeded",
  FAILED: "Failed",
  PENDING_TRANSFER: "Pending Transfer",
  PENDING_WIRE: "Pending Wire",
};

const STATUS_COLORS: Record<PaymentStatus, { bg: string; text: string }> = {
  INITIATED: { bg: "rgba(0,13,34,0.06)", text: "var(--brand-on-surface-variant)" },
  PROCESSING: { bg: "rgba(59,130,246,0.1)", text: "#3b82f6" },
  SUCCEEDED: { bg: "rgba(63,102,83,0.12)", text: "var(--brand-viridian)" },
  FAILED: { bg: "rgba(239,68,68,0.1)", text: "#ef4444" },
  PENDING_TRANSFER: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
  PENDING_WIRE: { bg: "rgba(245,158,11,0.1)", text: "#d97706" },
};

const METHOD_LABELS: Record<string, string> = {
  CARD: "Card",
  BANK_TRANSFER: "Bank Transfer",
  WIRE: "Wire",
};

const CURRENCY_SYMBOLS: Record<string, string> = {
  NGN: "₦",
  USD: "$",
  GBP: "£",
  EUR: "€",
};

function formatAmount(amountMinor: number, currency: string): string {
  const symbol = CURRENCY_SYMBOLS[currency] ?? currency;
  return `${symbol}${(amountMinor / 100).toLocaleString("en-NG", { minimumFractionDigits: 2 })}`;
}

function StatusChip({ status }: { status: PaymentStatus }) {
  const { bg, text } = STATUS_COLORS[status] ?? STATUS_COLORS.INITIATED;
  return (
    <span
      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
      style={{ backgroundColor: bg, color: text }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

function PaymentRow({ p, onClick }: { p: CustomerPayment; onClick: () => void }) {
  return (
    <tr
      className="hover:bg-gray-50 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-4 py-3 text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
        {new Date(p.dateCreated).toLocaleDateString("en-NG", { day: "numeric", month: "short", year: "numeric" })}
      </td>
      <td className="px-4 py-3 text-sm font-mono font-semibold" style={{ color: "var(--brand-navy)" }}>
        {p.vid}
      </td>
      <td className="px-4 py-3 text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>
        {formatAmount(p.amountMinor, p.currency)}
      </td>
      <td className="px-4 py-3 text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
        {METHOD_LABELS[p.method] ?? p.method}
      </td>
      <td className="px-4 py-3">
        <StatusChip status={p.status} />
      </td>
    </tr>
  );
}

const PAGE_SIZE = 20;

export default function PortalPaymentsPage() {
  const router = useRouter();
  const [page, setPage] = useState(0);
  const { data, isLoading, isError } = useMyPayments(page, PAGE_SIZE);

  const payments = data?.items ?? [];
  const total = data?.meta?.total ?? 0;
  const totalPages = data?.meta?.totalPages ?? 1;

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold font-display" style={{ color: "var(--brand-navy)" }}>
          Payment History
        </h1>
        <p className="text-sm mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
          All payments made for your property verifications.
        </p>
      </div>

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
            Failed to load payments. Please try again.
          </div>
        )}

        {!isLoading && !isError && payments.length === 0 && (
          <div className="py-20 text-center">
            <div
              className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
              style={{ backgroundColor: "rgba(63,102,83,0.08)" }}
            >
              <CreditCard className="w-6 h-6" style={{ color: "var(--brand-viridian)" }} />
            </div>
            <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
              No payments yet
            </p>
            <p className="text-xs mt-1" style={{ color: "var(--brand-on-surface-variant)" }}>
              Payments will appear here once you initiate a verification.
            </p>
          </div>
        )}

        {!isLoading && !isError && payments.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr style={{ borderBottom: "1px solid rgba(196,198,207,0.15)" }}>
                  {["Date", "VID", "Amount", "Method", "Status"].map((h) => (
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
                {payments.map((p) => (
                  <PaymentRow
                    key={p.id}
                    p={p}
                    onClick={() => router.push(ROUTES.PORTAL.VERIFICATION_DETAIL(p.verificationId))}
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
              {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((prev) => Math.max(0, prev - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 rounded-lg text-xs font-medium border transition-opacity disabled:opacity-40"
                style={{ borderColor: "rgba(196,198,207,0.4)", color: "var(--brand-navy)" }}
              >
                Previous
              </button>
              <button
                onClick={() => setPage((prev) => Math.min(totalPages - 1, prev + 1))}
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
