"use client";

import { useState } from "react";
import { AlertTriangle, CheckCircle, ChevronDown, ChevronUp, Loader2 } from "lucide-react";
import { useConflicts, useResolveConflictMutation } from "../libs/useAdminQueries";
import type { ConflictFlag } from "../libs/admin-service";

const STATUS_STYLES: Record<string, string> = {
  OPEN: "bg-red-50 border-red-200",
  OVERRIDDEN: "bg-green-50 border-green-200",
  TASK_REJECTED: "bg-gray-50 border-gray-200",
};

const SEVERITY_BADGE: Record<string, string> = {
  BLOCKER: "bg-red-100 text-red-700",
  WARNING: "bg-yellow-100 text-yellow-700",
};

interface ConflictItemProps {
  flag: ConflictFlag;
  vid: string;
}

function ConflictItem({ flag, vid }: ConflictItemProps) {
  const [expanded, setExpanded] = useState(flag.status === "OPEN");
  const [action, setAction] = useState<"OVERRIDE" | "REJECT_TASK">("OVERRIDE");
  const [note, setNote] = useState("");
  const [taskIdToReject, setTaskIdToReject] = useState("");
  const [error, setError] = useState("");

  const resolve = useResolveConflictMutation(vid);

  function handleResolve() {
    setError("");
    if (note.trim().length < 10) {
      setError("Resolution note must be at least 10 characters.");
      return;
    }
    if (action === "REJECT_TASK" && !taskIdToReject.trim()) {
      setError("Task ID to reject is required for REJECT_TASK action.");
      return;
    }
    resolve.mutate(
      { conflictId: flag.id, action, note: note.trim(), taskIdToReject: taskIdToReject.trim() || undefined },
      { onSuccess: () => { setNote(""); setExpanded(false); }, onError: () => setError("Failed to resolve conflict.") },
    );
  }

  const resolved = flag.status !== "OPEN";

  return (
    <div className={`rounded-lg border p-4 ${STATUS_STYLES[flag.status] ?? "bg-white border-gray-200"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${SEVERITY_BADGE[flag.severity] ?? ""}`}>
              {flag.severity}
            </span>
            <span className="text-xs font-mono text-gray-500">{flag.ruleId}</span>
            {resolved && (
              <span className="flex items-center gap-1 text-xs text-green-700">
                <CheckCircle className="h-3 w-3" />
                {flag.status === "OVERRIDDEN" ? "Overridden" : "Task rejected"}
              </span>
            )}
          </div>
          <p className="mt-1 text-sm text-gray-700">{flag.description}</p>
          {resolved && flag.resolutionNote && (
            <p className="mt-1 text-xs text-gray-500 italic">Note: {flag.resolutionNote}</p>
          )}
        </div>
        {!resolved && (
          <button
            onClick={() => setExpanded((e) => !e)}
            className="shrink-0 text-gray-400 hover:text-gray-600"
            style={{ cursor: "pointer" }}
          >
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        )}
      </div>

      {expanded && !resolved && (
        <div className="mt-4 space-y-3 border-t border-red-100 pt-3">
          <div className="flex gap-4">
            {(["OVERRIDE", "REJECT_TASK"] as const).map((a) => (
              <label key={a} className="flex items-center gap-1.5 text-sm cursor-pointer">
                <input
                  type="radio"
                  name={`action-${flag.id}`}
                  value={a}
                  checked={action === a}
                  onChange={() => setAction(a)}
                />
                {a === "OVERRIDE" ? "Override (keep findings)" : "Reject task (agent reworks)"}
              </label>
            ))}
          </div>

          {action === "REJECT_TASK" && (
            <input
              type="text"
              placeholder="Task ID to reject"
              value={taskIdToReject}
              onChange={(e) => setTaskIdToReject(e.target.value)}
              className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          )}

          <textarea
            rows={3}
            placeholder="Resolution note (required, min 10 chars)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
          />

          {error && <p className="text-xs text-red-600">{error}</p>}

          <button
            onClick={handleResolve}
            disabled={resolve.isPending}
            style={{ cursor: resolve.isPending ? "not-allowed" : "pointer" }}
            className="flex items-center gap-2 rounded bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {resolve.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
            Resolve conflict
          </button>
        </div>
      )}
    </div>
  );
}

interface Props {
  vid: string;
}

export default function ConflictPanel({ vid }: Props) {
  const { data, isLoading } = useConflicts(vid);
  const flags: ConflictFlag[] = (data as any)?.data ?? [];

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-gray-500 text-sm">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading conflicts…
      </div>
    );
  }

  if (flags.length === 0) {
    return (
      <div className="flex items-center gap-2 py-3 text-green-700 text-sm">
        <CheckCircle className="h-4 w-4" />
        No conflicts detected.
      </div>
    );
  }

  const openCount = flags.filter((f) => f.status === "OPEN").length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-red-600" />
        <span className="text-sm font-semibold text-gray-800">
          {openCount > 0 ? `${openCount} open conflict${openCount !== 1 ? "s" : ""} — must resolve before release` : "All conflicts resolved"}
        </span>
      </div>
      {flags.map((flag) => (
        <ConflictItem key={flag.id} flag={flag} vid={vid} />
      ))}
    </div>
  );
}
