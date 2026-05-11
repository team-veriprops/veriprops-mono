"use client";

import Link from "next/link";
import { ArrowLeft, Loader2, AlertTriangle } from "lucide-react";
import { useVerificationTasks } from "@components/admin/libs/useAdminQueries";
import EvidenceGallery from "@components/admin/tasks/EvidenceGallery";
import TaskReviewPanel from "@components/admin/tasks/TaskReviewPanel";
import { ROUTES } from "@lib/routes";

interface Props {
  taskId: string;
  vid: string;
}

export default function TaskReviewPageClient({ taskId, vid }: Props) {
  const { data: tasksRes, isLoading, error } = useVerificationTasks(vid);
  const tasks = (tasksRes as any)?.data ?? [];
  const task = tasks.find((t: any) => t.id === taskId) ?? null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="flex items-center gap-2 py-12 text-red-600">
        <AlertTriangle className="h-5 w-5" />
        <span>Task not found.</span>
      </div>
    );
  }

  const draftPayload = task.draftPayload ?? {};

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      {/* Back link */}
      {vid && (
        <Link
          href={ROUTES.ADMIN.VERIFICATION_DETAIL(vid)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to verification
        </Link>
      )}

      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-gray-900">
          Task Review — {task.role}
        </h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Task ID: <span className="font-mono">{task.id}</span>
        </p>
      </div>

      {/* Submission data */}
      <section className="rounded-xl border border-gray-200 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">Submission Data</h2>
        {Object.keys(draftPayload).length === 0 ? (
          <p className="text-sm text-gray-400 italic">No data submitted yet.</p>
        ) : (
          <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {Object.entries(draftPayload).map(([key, value]) => (
              <div key={key} className="flex flex-col">
                <dt className="text-xs text-gray-500 uppercase tracking-wide">
                  {key.replace(/_/g, " ")}
                </dt>
                <dd className="text-gray-800 font-medium break-words">
                  {typeof value === "boolean"
                    ? value ? "Yes" : "No"
                    : typeof value === "object"
                    ? JSON.stringify(value)
                    : String(value)}
                </dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      {/* Evidence gallery */}
      <section className="rounded-xl border border-gray-200 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">Evidence</h2>
        <EvidenceGallery task={task} evidence={[]} />
        <p className="text-xs text-gray-400">
          Evidence download is available only to assigned agents. Metadata shown here is read-only.
        </p>
      </section>

      {/* Review actions */}
      <section className="rounded-xl border border-gray-200 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-700">Review Decision</h2>
        <TaskReviewPanel task={task} vid={vid} />
      </section>
    </div>
  );
}
