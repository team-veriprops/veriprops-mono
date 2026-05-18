"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { Shield, Loader2, AlertTriangle } from "lucide-react";
import AccountShell from "@components/account/AccountShell";

interface ErasureRequestDto {
  id: string;
  userId: string;
  reason: string | null;
  status: "PENDING" | "APPROVED" | "EXECUTED" | "REJECTED";
  requestedAt: string;
  reviewedAt: string | null;
  executedAt: string | null;
  rejectionReason: string | null;
}

const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
  PENDING:  { bg: "rgba(176,125,0,0.08)",   color: "var(--warning)" },
  APPROVED: { bg: "rgba(63,102,83,0.08)",   color: "var(--brand-viridian)" },
  EXECUTED: { bg: "rgba(63,102,83,0.12)",   color: "var(--brand-viridian)" },
  REJECTED: { bg: "rgba(211,47,47,0.08)",   color: "var(--danger)" },
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export default function DataPrivacyPage() {
  const qc = useQueryClient();
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useQuery<{ data: ErasureRequestDto | null }>({
    queryKey: ["account", "erasure-request"],
    queryFn: () => httpClient.get("/account/erasure-request"),
    staleTime: 60_000,
  });

  const erasureRequest = (data as any)?.data ?? null;

  const requestMutation = useMutation({
    mutationFn: () =>
      httpClient.post("/account/erasure-request", { reason: reason.trim() || null }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["account", "erasure-request"] });
      setError(null);
      setConfirmed(false);
      setReason("");
    },
    onError: (e: any) => {
      setError(e?.message ?? "Failed to submit erasure request.");
    },
  });

  return (
    <AccountShell
      title="Data & privacy"
      subtitle="Manage your personal data in compliance with NDPR."
    >
      {/* What we retain */}
      <div
        className="rounded-xl p-5 mb-6"
        style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
      >
        <div className="flex items-center gap-2 mb-3">
          <Shield className="h-4 w-4" style={{ color: "var(--brand-viridian)" }} />
          <h2 className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>What we retain</h2>
        </div>
        <ul className="space-y-1.5">
          {[
            "Account details (name, email, phone) — up to 7 years after last activity",
            "Verification records — retained indefinitely for legal compliance",
            "Audit logs — retained indefinitely per NDPR §19.2",
            "Consent records — retained for the duration of our relationship with you",
          ].map((item) => (
            <li key={item} className="text-sm flex items-start gap-2" style={{ color: "var(--brand-on-surface-variant)" }}>
              <span className="mt-1.5 w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: "var(--brand-viridian)" }} />
              {item}
            </li>
          ))}
        </ul>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--brand-viridian)" }} />
        </div>
      )}

      {!isLoading && erasureRequest && (
        <div
          className="rounded-xl p-5 mb-6"
          style={{ backgroundColor: "var(--brand-surface-card)", boxShadow: "var(--shadow-card)" }}
        >
          <h2 className="text-sm font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>Your erasure request</h2>
          <div className="flex items-center gap-3">
            <span
              className="text-xs px-2.5 py-1 rounded-full font-semibold"
              style={STATUS_STYLES[erasureRequest.status]}
            >
              {erasureRequest.status}
            </span>
            <span className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
              Submitted {formatDate(erasureRequest.requestedAt)}
            </span>
          </div>
          {erasureRequest.rejectionReason && (
            <p className="text-sm mt-2" style={{ color: "var(--danger)" }}>
              Rejected: {erasureRequest.rejectionReason}
            </p>
          )}
          {erasureRequest.executedAt && (
            <p className="text-sm mt-2" style={{ color: "var(--brand-viridian)" }}>
              Data anonymised on {formatDate(erasureRequest.executedAt)}.
            </p>
          )}
        </div>
      )}

      {!isLoading && !erasureRequest && (
        <div
          className="rounded-xl p-5"
          style={{ border: "1px solid rgba(211,47,47,0.2)", backgroundColor: "rgba(211,47,47,0.03)" }}
        >
          <div className="flex items-start gap-3 mb-5">
            <AlertTriangle className="h-5 w-5 shrink-0 mt-0.5" style={{ color: "var(--danger)" }} />
            <div>
              <h2 className="text-sm font-semibold" style={{ color: "var(--danger)" }}>Request account erasure</h2>
              <p className="text-xs mt-1 leading-relaxed" style={{ color: "var(--brand-on-surface-variant)" }}>
                This action cannot be undone. Your personal information will be anonymised once the request is
                approved. Active verifications must be completed or cancelled before erasure can be executed.
              </p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium block mb-1.5" style={{ color: "var(--brand-navy)" }}>
                Reason (optional)
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Tell us why you're requesting erasure…"
                rows={3}
                className="w-full rounded-lg px-3 py-2 text-sm resize-none"
                style={{ border: "1px solid rgba(196,198,207,0.4)", color: "var(--brand-navy)" }}
              />
            </div>

            <label className="flex items-start gap-2.5 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-0.5"
              />
              <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
                I understand this will anonymise my account details and I cannot undo this action.
              </span>
            </label>

            {error && <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}

            <button
              onClick={() => requestMutation.mutate()}
              disabled={!confirmed || requestMutation.isPending}
              className="w-full rounded-lg text-white text-sm font-semibold py-2.5 transition-opacity disabled:opacity-50"
              style={{ backgroundColor: "var(--danger)", cursor: !confirmed || requestMutation.isPending ? "default" : "pointer" }}
            >
              {requestMutation.isPending ? "Submitting…" : "Submit erasure request"}
            </button>
          </div>
        </div>
      )}
    </AccountShell>
  );
}
