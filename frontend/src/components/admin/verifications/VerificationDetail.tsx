"use client";

import { useState } from "react";
import Link from "next/link";
import { useAdminVerificationDetail, useVerificationTasks } from "../libs/useAdminQueries";
import VerificationStatusBadge from "./VerificationStatusBadge";
import AdminActionPanel from "./AdminActionPanel";
import NotesList from "./NotesList";
import AssignmentModal from "./AssignmentModal";
import ConflictBadge from "./ConflictBadge";
import ConflictPanel from "./ConflictPanel";
import ReleaseReportPanel from "./ReleaseReportPanel";
import { useConflicts } from "../libs/useAdminQueries";
import TrustScoreBadge from "@components/shared/TrustScoreBadge";
import type { Task, TaskRole, TaskStatus } from "../libs/admin-service";
import { User, Loader2, AlertTriangle } from "lucide-react";
import { ROUTES } from "@lib/routes";

const TASK_STATUS_COLORS: Record<TaskStatus, string> = {
  PENDING: "bg-gray-100 text-gray-600",
  ASSIGNED: "bg-blue-100 text-blue-700",
  ACCEPTED: "bg-cyan-100 text-cyan-700",
  IN_PROGRESS: "bg-yellow-100 text-yellow-800",
  SUBMITTED: "bg-purple-100 text-purple-700",
  APPROVED: "bg-green-100 text-green-700",
  REJECTED: "bg-red-100 text-red-700",
};

interface Props { vid: string }

export default function VerificationDetail({ vid }: Props) {
  const { data: detailRes, isLoading, error } = useAdminVerificationDetail(vid);
  const { data: tasksRes } = useVerificationTasks(vid);
  const { data: conflictsRes } = useConflicts(vid);
  const [assignModal, setAssignModal] = useState<TaskRole | null>(null);

  const verification = (detailRes as any)?.data ?? null;
  const tasks: Task[] = (tasksRes as any)?.data ?? [];
  const conflicts = (conflictsRes as any)?.data ?? [];
  const openConflictCount = conflicts.filter((f: any) => f.status === "OPEN").length;
  const allTasksApproved = tasks.length > 0 && tasks.every((t) => t.status === "APPROVED");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    );
  }
  if (error || !verification) {
    return (
      <div className="flex items-center gap-2 py-12 text-red-600">
        <AlertTriangle className="h-5 w-5" />
        <span>Verification not found.</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 font-mono">{verification.vid}</h1>
          <div className="flex items-center gap-3 mt-1">
            <VerificationStatusBadge status={verification.status} />
            <span className="text-sm text-gray-500">{verification.tier}</span>
            {verification.status === "UNDER_REVIEW" && (
              <ConflictBadge openCount={openConflictCount} />
            )}
            {verification.trustScore !== null && verification.trustScore !== undefined && (
              <TrustScoreBadge score={Number(verification.trustScore)} size="sm" />
            )}
          </div>
        </div>
        <AdminActionPanel verification={verification} />
      </div>

      {/* Property info */}
      {verification.property && (
        <div className="rounded-lg border border-gray-200 p-4">
          <h2 className="text-sm font-semibold text-gray-700 mb-2">Property</h2>
          <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
            <span>State: <strong>{verification.property.state ?? "—"}</strong></span>
            <span>LGA: <strong>{verification.property.lga ?? "—"}</strong></span>
            <span className="col-span-2">Address: <strong>{verification.property.addressLine ?? "—"}</strong></span>
          </div>
        </div>
      )}

      {/* Tasks */}
      <div>
        <h2 className="text-sm font-semibold text-gray-700 mb-2">Tasks</h2>
        {tasks.length === 0 ? (
          <p className="text-sm text-gray-400 italic">No tasks yet.</p>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="flex items-center justify-between rounded-lg border border-gray-200 px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-gray-900 w-20">{task.role}</span>
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${TASK_STATUS_COLORS[task.status]}`}
                  >
                    {task.status.replace("_", " ")}
                  </span>
                  {task.agentId && (
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      <User className="h-3 w-3" />
                      {task.agentId.slice(0, 8)}…
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  {(task.status === "PENDING" || task.status === "ASSIGNED") && (
                    <button
                      style={{ cursor: "pointer" }}
                      onClick={() => setAssignModal(task.role as TaskRole)}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-medium border border-indigo-200 rounded px-2 py-1"
                    >
                      {task.status === "ASSIGNED" ? "Reassign" : "Assign Agent"}
                    </button>
                  )}
                  {(task.status === "SUBMITTED" || task.status === "APPROVED") && (
                    <Link
                      href={`${ROUTES.ADMIN.TASK_REVIEW(task.id)}?vid=${vid}`}
                      className="text-xs text-emerald-700 hover:text-emerald-900 font-medium border border-emerald-200 rounded px-2 py-1"
                    >
                      {task.status === "APPROVED" ? "Reopen" : "Review"}
                    </Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Conflict panel + release — shown when under review */}
      {verification.status === "UNDER_REVIEW" && (
        <>
          <div className="rounded-lg border border-red-100 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Conflict Detection</h2>
            <ConflictPanel vid={vid} />
          </div>
          <ReleaseReportPanel
            vid={vid}
            hasOpenConflicts={openConflictCount > 0}
            allTasksApproved={allTasksApproved}
          />
        </>
      )}

      {/* Notes */}
      <NotesList vid={vid} notes={verification.notes ?? []} />

      {/* Assignment modal */}
      {assignModal && (
        <AssignmentModal
          vid={vid}
          role={assignModal}
          open={!!assignModal}
          onClose={() => setAssignModal(null)}
        />
      )}
    </div>
  );
}
