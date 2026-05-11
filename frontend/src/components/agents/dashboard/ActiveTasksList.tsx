"use client";

import { useRouter } from "next/navigation";
import { useActiveTasks } from "../libs/useAgentTaskQueries";
import type { Task, TaskRole, TaskStatus } from "../libs/agent-service";
import { ROUTES } from "@/lib/routes";
import { CheckCircle2, Clock } from "lucide-react";

const STATUS_LABELS: Partial<Record<TaskStatus, string>> = {
  ACCEPTED: "Accepted",
  IN_PROGRESS: "In Progress",
};

export default function ActiveTasksList() {
  const router = useRouter();
  const { data, isLoading } = useActiveTasks();
  const tasks: Task[] = (data as any)?.data ?? [];

  if (isLoading) return <div className="py-6 text-center text-gray-400 text-sm">Loading…</div>;
  if (tasks.length === 0) {
    return (
      <div className="py-8 text-center text-gray-400">
        <Clock className="h-7 w-7 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No active tasks.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => (
        <div
          key={task.id}
          onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
          style={{ cursor: "pointer" }}
          className="flex items-center justify-between rounded-lg border border-gray-200 bg-white hover:border-indigo-300 transition-colors px-4 py-3"
        >
          <div>
            <p className="text-sm font-medium text-gray-900">{task.role} Verification</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {task.acceptedAt ? `Accepted ${new Date(task.acceptedAt).toLocaleDateString()}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-yellow-700 bg-yellow-100 px-2 py-0.5 rounded">
              {STATUS_LABELS[task.status as TaskStatus] ?? task.status}
            </span>
            <span className="text-indigo-600 text-xs font-medium">View →</span>
          </div>
        </div>
      ))}
    </div>
  );
}
