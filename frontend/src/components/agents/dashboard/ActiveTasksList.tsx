"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Clock } from "lucide-react";
import { useActiveTasks } from "../libs/useAgentTaskQueries";
import type { Task, TaskStatus } from "../libs/agent-service";
import { ROUTES } from "@/lib/routes";

const STATUS_LABELS: Partial<Record<TaskStatus, string>> = {
  ACCEPTED: "Accepted",
  IN_PROGRESS: "In Progress",
};

const STATUS_COLORS: Partial<Record<TaskStatus, { color: string; bg: string }>> = {
  ACCEPTED: { color: "#d97706", bg: "rgba(245,158,11,0.1)" },
  IN_PROGRESS: { color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
};

function ElapsedTime({ from }: { from: string }) {
  const [label, setLabel] = useState("");

  useEffect(() => {
    function compute() {
      const diff = Date.now() - new Date(from).getTime();
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      setLabel(h > 0 ? `${h}h ${m}m` : `${m}m`);
    }
    compute();
    const id = setInterval(compute, 60_000);
    return () => clearInterval(id);
  }, [from]);

  if (!label) return null;
  return (
    <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
      {label} elapsed
    </span>
  );
}

export default function ActiveTasksList() {
  const router = useRouter();
  const { data, isLoading } = useActiveTasks();
  const tasks: Task[] = (data as any)?.data ?? [];

  if (isLoading) {
    return <div className="py-6 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>;
  }

  if (tasks.length === 0) {
    return (
      <div className="py-8 text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        <Clock className="h-7 w-7 mx-auto mb-2 opacity-30" />
        <p className="text-sm">No active tasks right now.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => {
        const chip = STATUS_COLORS[task.status as TaskStatus] ?? { color: "#6b7280", bg: "#f3f4f6" };
        return (
          <div
            key={task.id}
            onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
            className="flex items-center justify-between rounded-xl border px-4 py-3 transition-all hover:shadow-sm"
            style={{
              backgroundColor: "#fff",
              borderColor: "rgba(196,198,207,0.2)",
              cursor: "pointer",
            }}
          >
            <div className="min-w-0">
              <p className="text-sm font-medium" style={{ color: "var(--brand-navy)" }}>
                {task.role} Verification
              </p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs font-mono" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {task.verificationId.slice(0, 10)}…
                </span>
                {task.status === "ACCEPTED" && task.acceptedAt && (
                  <ElapsedTime from={task.acceptedAt} />
                )}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span
                className="text-xs font-semibold px-2.5 py-0.5 rounded-full"
                style={{ color: chip.color, backgroundColor: chip.bg }}
              >
                {STATUS_LABELS[task.status as TaskStatus] ?? task.status}
              </span>
              <span className="text-xs font-medium" style={{ color: "var(--brand-viridian)" }}>
                View →
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
