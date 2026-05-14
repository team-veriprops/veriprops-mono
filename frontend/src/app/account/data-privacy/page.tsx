"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { httpClient } from "@/containers";
import { Shield, Loader2, AlertTriangle } from "lucide-react";

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

const STATUS_STYLES: Record<string, string> = {
  PENDING: "bg-yellow-100 text-yellow-800",
  APPROVED: "bg-blue-100 text-blue-700",
  EXECUTED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
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
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="flex items-start gap-3 mb-6">
        <Shield className="h-6 w-6 text-indigo-500 mt-0.5 shrink-0" />
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Data Privacy & Retention</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Manage your personal data in compliance with NDPR
          </p>
        </div>
      </div>

      {/* What we retain */}
      <div className="rounded-lg border border-gray-200 p-5 mb-6 space-y-2">
        <h2 className="text-sm font-semibold text-gray-800">What we retain</h2>
        <ul className="text-sm text-gray-600 space-y-1 list-disc list-inside">
          <li>Account details (name, email, phone) — up to 7 years after last activity</li>
          <li>Verification records — retained indefinitely for legal compliance</li>
          <li>Audit logs — retained indefinitely per NDPR §19.2</li>
          <li>Consent records — retained for the duration of our relationship with you</li>
        </ul>
      </div>

      {/* Current request status */}
      {isLoading && (
        <div className="flex items-center justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-indigo-500" />
        </div>
      )}

      {!isLoading && erasureRequest && (
        <div className="rounded-lg border border-gray-200 p-5 mb-6">
          <h2 className="text-sm font-semibold text-gray-800 mb-3">Your Erasure Request</h2>
          <div className="flex items-center gap-3">
            <span
              className={`text-xs px-2 py-0.5 rounded font-medium ${STATUS_STYLES[erasureRequest.status]}`}
            >
              {erasureRequest.status}
            </span>
            <span className="text-sm text-gray-500">
              Submitted {formatDate(erasureRequest.requestedAt)}
            </span>
          </div>
          {erasureRequest.rejectionReason && (
            <p className="text-sm text-red-600 mt-2">
              Rejected: {erasureRequest.rejectionReason}
            </p>
          )}
          {erasureRequest.executedAt && (
            <p className="text-sm text-green-700 mt-2">
              Data anonymised on {formatDate(erasureRequest.executedAt)}.
            </p>
          )}
        </div>
      )}

      {/* Request form — only show if no active request */}
      {!isLoading && !erasureRequest && (
        <div className="rounded-lg border border-red-100 bg-red-50 p-5">
          <div className="flex items-start gap-2 mb-4">
            <AlertTriangle className="h-5 w-5 text-red-500 shrink-0 mt-0.5" />
            <div>
              <h2 className="text-sm font-semibold text-red-800">Request Account Erasure</h2>
              <p className="text-xs text-red-700 mt-0.5">
                This action cannot be undone. Your personal information will be anonymised
                once the request is approved by our team. Active verifications must be
                completed or cancelled before erasure can be executed.
              </p>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-700 block mb-1">
                Reason (optional)
              </label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Tell us why you're requesting erasure…"
                rows={3}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm resize-none"
              />
            </div>

            <label className="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={confirmed}
                onChange={(e) => setConfirmed(e.target.checked)}
                className="mt-0.5"
              />
              <span className="text-xs text-gray-700">
                I understand this will anonymise my account details and I cannot undo this
                action.
              </span>
            </label>

            {error && <p className="text-sm text-red-600">{error}</p>}

            <button
              onClick={() => requestMutation.mutate()}
              disabled={!confirmed || requestMutation.isPending}
              style={{ cursor: !confirmed || requestMutation.isPending ? "default" : "pointer" }}
              className="w-full rounded bg-red-600 text-white text-sm font-medium py-2 hover:bg-red-700 disabled:opacity-50"
            >
              {requestMutation.isPending ? "Submitting…" : "Submit Erasure Request"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
