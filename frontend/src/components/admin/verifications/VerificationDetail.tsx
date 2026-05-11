"use client";

import { useState } from "react";
import { useAdminVerificationDetail, useVerificationTasks } from "../libs/useAdminQueries";
import VerificationStatusBadge from "./VerificationStatusBadge";
import AdminActionPanel from "./AdminActionPanel";
import NotesList from "./NotesList";
import AssignmentModal from "./AssignmentModal";
import type { Task, TaskRole, TaskStatus } from "../libs/admin-service";
import { User, Loader2, AlertTriangle } from "lucide-react";

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
  const [assignModal, setAssignModal] = useState<TaskRole | null>(null);

  const verification = (detailRes as any)?.data ?? null;
  const tasks: Task[] = (tasksRes as any)?.data ?? [];

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
                {(task.status === "PENDING" || task.status === "ASSIGNED") && (
                  <button
                    style={{ cursor: "pointer" }}
                    onClick={() => setAssignModal(task.role as TaskRole)}
                    className="text-xs text-indigo-600 hover:text-indigo-800 font-medium border border-indigo-200 rounded px-2 py-1"
                  >
                    {task.status === "ASSIGNED" ? "Reassign" : "Assign Agent"}
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

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
