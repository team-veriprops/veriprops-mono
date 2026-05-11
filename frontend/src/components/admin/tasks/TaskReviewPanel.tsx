"use client";

import { useState } from "react";
import { CheckCircle2, XCircle, RotateCcw, AlertTriangle } from "lucide-react";
import type { Task } from "@components/admin/libs/admin-service";
import {
  useApproveTaskMutation,
  useRejectTaskMutation,
  useReopenTaskMutation,
} from "./libs/useTaskReviewQueries";

const MIN_REASON = 30;

interface Props {
  task: Task;
  vid: string;
  onSuccess?: () => void;
}

type Dialog = "reject" | "reopen" | null;

export default function TaskReviewPanel({ task, vid, onSuccess }: Props) {
  const [dialog, setDialog] = useState<Dialog>(null);
  const [reason, setReason] = useState("");
  const [approveNote, setApproveNote] = useState("");

  const approve = useApproveTaskMutation(vid);
  const reject = useRejectTaskMutation(vid);
  const reopen = useReopenTaskMutation(vid);

  const busy = approve.isPending || reject.isPending || reopen.isPending;
  const reasonTooShort = reason.trim().length < MIN_REASON;

  function handleApprove() {
    approve.mutate(
      { taskId: task.id, note: approveNote || undefined },
      { onSuccess: () => { setApproveNote(""); onSuccess?.(); } },
    );
  }

  function handleReject() {
    if (reasonTooShort) return;
    reject.mutate(
      { taskId: task.id, reason },
      { onSuccess: () => { setDialog(null); setReason(""); onSuccess?.(); } },
    );
  }

  function handleReopen() {
    if (reasonTooShort) return;
    reopen.mutate(
      { taskId: task.id, reason },
      { onSuccess: () => { setDialog(null); setReason(""); onSuccess?.(); } },
    );
  }

  return (
    <div className="space-y-4">
      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        {task.status === "SUBMITTED" && (
          <>
            <button
              style={{ cursor: "pointer" }}
              disabled={busy}
              onClick={handleApprove}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm font-medium hover:bg-emerald-700 disabled:opacity-50"
            >
              <CheckCircle2 className="h-4 w-4" />
              Approve
            </button>
            <button
              style={{ cursor: "pointer" }}
              disabled={busy}
              onClick={() => { setDialog("reject"); setReason(""); }}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium hover:bg-red-700 disabled:opacity-50"
            >
              <XCircle className="h-4 w-4" />
              Reject
            </button>
          </>
        )}
        {task.status === "APPROVED" && (
          <button
            style={{ cursor: "pointer" }}
            disabled={busy}
            onClick={() => { setDialog("reopen"); setReason(""); }}
            className="flex items-center gap-2 px-4 py-2 rounded-lg border border-amber-500 text-amber-700 text-sm font-medium hover:bg-amber-50 disabled:opacity-50"
          >
            <RotateCcw className="h-4 w-4" />
            Reopen
          </button>
        )}
        {task.status !== "SUBMITTED" && task.status !== "APPROVED" && (
          <p className="text-sm text-gray-400 italic">
            Task is not in a reviewable state ({task.status}).
          </p>
        )}
      </div>

      {/* Optional approve note */}
      {task.status === "SUBMITTED" && (
        <div>
          <label className="block text-xs font-medium text-gray-600 mb-1">
            Approval note (optional)
          </label>
          <input
            type="text"
            value={approveNote}
            onChange={(e) => setApproveNote(e.target.value)}
            placeholder="Add a note for this approval…"
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
        </div>
      )}

      {/* Error banners */}
      {approve.isError && (
        <div className="flex items-center gap-2 text-sm text-red-600">
          <AlertTriangle className="h-4 w-4" />
          {(approve.error as any)?.message ?? "Approval failed. Try again."}
        </div>
      )}

      {/* Reject / Reopen dialog */}
      {dialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="w-full max-w-md mx-4 bg-white rounded-xl shadow-xl p-6 space-y-4">
            <h2 className="text-base font-semibold text-gray-900">
              {dialog === "reject" ? "Reject Task" : "Reopen Task"}
            </h2>
            <p className="text-sm text-gray-500">
              {dialog === "reject"
                ? "Provide a reason. The agent will see this and can resubmit."
                : "Provide a reason for reopening. This will return the task to the agent."}
            </p>
            <div>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={4}
                placeholder={`Reason (minimum ${MIN_REASON} characters)…`}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 resize-none"
              />
              <p className={`text-xs mt-1 ${reasonTooShort ? "text-red-500" : "text-gray-400"}`}>
                {reason.trim().length}/{MIN_REASON} characters minimum
              </p>
            </div>
            <div className="flex justify-end gap-3">
              <button
                style={{ cursor: "pointer" }}
                onClick={() => setDialog(null)}
                className="px-4 py-2 rounded-lg border border-gray-200 text-sm text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                style={{ cursor: "pointer" }}
                disabled={reasonTooShort || busy}
                onClick={dialog === "reject" ? handleReject : handleReopen}
                className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 disabled:opacity-50"
              >
                {busy ? "Saving…" : dialog === "reject" ? "Confirm Rejection" : "Confirm Reopen"}
              </button>
            </div>
            {(reject.isError || reopen.isError) && (
              <p className="text-sm text-red-600">
                {((dialog === "reject" ? reject.error : reopen.error) as any)?.message ?? "Action failed."}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
