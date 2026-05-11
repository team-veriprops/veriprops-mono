"use client";

import { useState } from "react";
import { CheckCircle, XCircle, Loader2, AlertTriangle } from "lucide-react";
import { useReleaseReportMutation, useFailReleaseMutation } from "../libs/useAdminQueries";

const MIN_FAIL_REASON = 50;

interface Props {
  vid: string;
  hasOpenConflicts: boolean;
  allTasksApproved: boolean;
}

export default function ReleaseReportPanel({ vid, hasOpenConflicts, allTasksApproved }: Props) {
  const [showFailDialog, setShowFailDialog] = useState(false);
  const [failReason, setFailReason] = useState("");
  const [error, setError] = useState("");

  const release = useReleaseReportMutation();
  const fail = useFailReleaseMutation();

  const canRelease = allTasksApproved && !hasOpenConflicts;

  function handleRelease() {
    setError("");
    release.mutate(vid, {
      onError: (e: any) => setError(e?.message ?? "Release failed."),
    });
  }

  function handleFail() {
    setError("");
    if (failReason.trim().length < MIN_FAIL_REASON) {
      setError(`Reason must be at least ${MIN_FAIL_REASON} characters.`);
      return;
    }
    fail.mutate(
      { vid, reason: failReason.trim() },
      {
        onSuccess: () => { setShowFailDialog(false); setFailReason(""); },
        onError: (e: any) => setError(e?.message ?? "Failed."),
      },
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 p-4 space-y-3">
      <h2 className="text-sm font-semibold text-gray-700">Report Release</h2>

      {!canRelease && (
        <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 rounded p-2">
          <AlertTriangle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>
            {!allTasksApproved && "All tasks must be approved. "}
            {hasOpenConflicts && "Open conflicts must be resolved first."}
          </span>
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleRelease}
          disabled={!canRelease || release.isPending}
          style={{ cursor: canRelease && !release.isPending ? "pointer" : "not-allowed" }}
          className="flex items-center gap-2 rounded bg-green-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {release.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle className="h-3.5 w-3.5" />}
          Release Report
        </button>
        <button
          onClick={() => setShowFailDialog(true)}
          style={{ cursor: "pointer" }}
          className="flex items-center gap-2 rounded border border-red-300 px-4 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          <XCircle className="h-3.5 w-3.5" />
          Fail Verification
        </button>
      </div>

      {error && !showFailDialog && (
        <p className="text-xs text-red-600">{error}</p>
      )}

      {showFailDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl space-y-4">
            <h3 className="text-base font-semibold text-gray-900">Fail Verification</h3>
            <p className="text-sm text-gray-500">
              This is irreversible. Provide a detailed reason (minimum {MIN_FAIL_REASON} characters).
            </p>
            <textarea
              rows={4}
              value={failReason}
              onChange={(e) => { setFailReason(e.target.value); setError(""); }}
              placeholder="Describe why this verification cannot be completed…"
              className="w-full rounded border border-gray-300 px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-red-500"
            />
            <p className="text-xs text-gray-400">{failReason.length} / {MIN_FAIL_REASON} min chars</p>
            {error && <p className="text-xs text-red-600">{error}</p>}
            <div className="flex justify-end gap-2">
              <button
                onClick={() => { setShowFailDialog(false); setError(""); setFailReason(""); }}
                className="rounded border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
                style={{ cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={handleFail}
                disabled={fail.isPending}
                style={{ cursor: fail.isPending ? "not-allowed" : "pointer" }}
                className="flex items-center gap-2 rounded bg-red-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-60"
              >
                {fail.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
                Confirm Fail
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
