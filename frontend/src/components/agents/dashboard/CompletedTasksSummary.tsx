"use client";

import { useCompletedTasks } from "../libs/useAgentTaskQueries";
import type { Task } from "../libs/agent-service";
import { CheckCircle2 } from "lucide-react";

export default function CompletedTasksSummary() {
  const { data, isLoading } = useCompletedTasks();
  const tasks: Task[] = (data as any)?.data ?? [];

  const approved = tasks.filter((t) => t.status === "APPROVED").length;
  const submitted = tasks.filter((t) => t.status === "SUBMITTED").length;

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4 text-green-500" />
        <h3 className="text-sm font-semibold text-gray-700">Completed</h3>
      </div>
      {isLoading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : (
        <div className="flex gap-6">
          <div>
            <p className="text-2xl font-bold text-green-600">{approved}</p>
            <p className="text-xs text-gray-500">Approved</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-purple-600">{submitted}</p>
            <p className="text-xs text-gray-500">Under Review</p>
          </div>
          <div>
            <p className="text-2xl font-bold text-gray-700">{tasks.length}</p>
            <p className="text-xs text-gray-500">Total</p>
          </div>
        </div>
      )}
    </div>
  );
}
