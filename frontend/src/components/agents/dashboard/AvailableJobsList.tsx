"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAvailableTasks, useAcceptTaskMutation } from "../libs/useAgentTaskQueries";
import type { TaskRole, Task } from "../libs/agent-service";
import { ROUTES } from "@/lib/routes";
import { getErrorMessage } from "@lib/utils";
import { MapPin, Briefcase, AlertCircle } from "lucide-react";

const ROLE_COLORS: Record<TaskRole, string> = {
  FIELD: "bg-green-100 text-green-700",
  SURVEYOR: "bg-blue-100 text-blue-700",
  REGISTRY: "bg-purple-100 text-purple-700",
  LAWYER: "bg-orange-100 text-orange-700",
};

interface Props {
  role: TaskRole;
}

export default function AvailableJobsList({ role }: Props) {
  const router = useRouter();
  const { data, isLoading } = useAvailableTasks(role);
  const accept = useAcceptTaskMutation();
  const [errors, setErrors] = useState<Record<string, string>>({});

  const tasks: Task[] = (data as any)?.data ?? [];

  const handleAccept = async (task: Task, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await accept.mutateAsync(task.id);
      router.push(ROUTES.AGENT.TASK_DETAIL(task.id));
    } catch (err) {
      const msg = getErrorMessage(err as Error);
      setErrors((prev) => ({ ...prev, [task.id]: msg }));
      // Error clears after 4 s
      setTimeout(() => setErrors((prev) => { const n = { ...prev }; delete n[task.id]; return n; }), 4000);
    }
  };

  if (isLoading) {
    return <div className="py-8 text-center text-gray-400 text-sm">Loading available jobs…</div>;
  }
  if (tasks.length === 0) {
    return (
      <div className="py-10 text-center text-gray-400">
        <Briefcase className="h-8 w-8 mx-auto mb-2 opacity-40" />
        <p className="text-sm">No available jobs for your role right now.</p>
        <p className="text-xs mt-1">Check back later — tasks appear when verifications reach you.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <div
          key={task.id}
          onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
          style={{ cursor: "pointer" }}
          className="rounded-lg border border-gray-200 bg-white hover:border-indigo-300 hover:shadow-sm transition-all p-4"
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${ROLE_COLORS[task.role as TaskRole]}`}
                >
                  {task.role}
                </span>
                <span className="text-xs text-gray-500 font-mono truncate">
                  {task.verificationId.slice(0, 8)}…
                </span>
              </div>
              {errors[task.id] && (
                <div className="flex items-center gap-1 mt-2 text-xs text-red-600">
                  <AlertCircle className="h-3 w-3 flex-shrink-0" />
                  {errors[task.id]}
                </div>
              )}
            </div>
            <button
              onClick={(e) => handleAccept(task, e)}
              style={{ cursor: "pointer" }}
              disabled={accept.isPending}
              className="flex-shrink-0 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-medium rounded transition-colors disabled:opacity-60"
            >
              {accept.isPending ? "Accepting…" : "Accept"}
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Released {task.poolReleasedAt ? new Date(task.poolReleasedAt).toLocaleString() : "—"}
          </p>
        </div>
      ))}
    </div>
  );
}
