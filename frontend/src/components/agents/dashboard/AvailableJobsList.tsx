"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Briefcase, AlertCircle } from "lucide-react";
import { useAvailableTasks, useAcceptTaskMutation } from "../libs/useAgentTaskQueries";
import type { TaskRole, Task } from "../libs/agent-service";
import { ROUTES } from "@/lib/routes";
import { getErrorMessage } from "@lib/utils";

const ROLE_COLORS: Record<TaskRole, { color: string; bg: string }> = {
  FIELD:    { color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
  SURVEYOR: { color: "#2563eb", bg: "rgba(37,99,235,0.08)" },
  REGISTRY: { color: "#7c3aed", bg: "rgba(124,58,237,0.08)" },
  LAWYER:   { color: "#d97706", bg: "rgba(245,158,11,0.08)" },
};

const ROLE_LABELS: Record<TaskRole, string> = {
  FIELD: "Field",
  SURVEYOR: "Surveyor",
  REGISTRY: "Registry",
  LAWYER: "Lawyer",
};

interface Props {
  roles: TaskRole[];
}

function JobList({ role }: { role: TaskRole }) {
  const router = useRouter();
  const { data, isLoading } = useAvailableTasks(role);
  const accept = useAcceptTaskMutation();
  const [errors, setErrors] = useState<Record<string, string>>({});

  const tasks: Task[] = (data as any)?.data ?? [];
  const chipStyle = ROLE_COLORS[role];

  async function handleAccept(task: Task, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      await accept.mutateAsync(task.id);
      router.push(ROUTES.AGENT.TASK_DETAIL(task.id));
    } catch (err) {
      const msg = getErrorMessage(err as Error);
      setErrors((prev) => ({ ...prev, [task.id]: msg }));
      setTimeout(
        () => setErrors((prev) => { const n = { ...prev }; delete n[task.id]; return n; }),
        4000,
      );
    }
  }

  if (isLoading) {
    return <div className="py-8 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading jobs…</div>;
  }

  if (tasks.length === 0) {
    return (
      <div className="py-10 text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        <Briefcase className="h-8 w-8 mx-auto mb-2 opacity-30" />
        <p className="text-sm">No available {ROLE_LABELS[role].toLowerCase()} jobs right now.</p>
        <p className="text-xs mt-1 opacity-70">Tasks appear when verifications match your coverage area.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {tasks.map((task) => (
        <div
          key={task.id}
          onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
          className="rounded-xl border p-4 transition-all hover:shadow-sm"
          style={{ backgroundColor: "#fff", borderColor: "rgba(196,198,207,0.2)", cursor: "pointer" }}
        >
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className="px-2 py-0.5 rounded-full text-xs font-semibold"
                  style={{ color: chipStyle.color, backgroundColor: chipStyle.bg }}
                >
                  {ROLE_LABELS[role]}
                </span>
                <span className="text-xs font-mono truncate" style={{ color: "var(--brand-on-surface-variant)" }}>
                  {task.verificationId.slice(0, 10)}…
                </span>
              </div>
              {errors[task.id] && (
                <div className="flex items-center gap-1 mt-2 text-xs text-red-600">
                  <AlertCircle className="h-3 w-3 shrink-0" />
                  {errors[task.id]}
                </div>
              )}
            </div>
            <button
              onClick={(e) => handleAccept(task, e)}
              disabled={accept.isPending}
              className="shrink-0 px-3 py-1.5 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-60"
              style={{ backgroundColor: "var(--brand-viridian)", cursor: "pointer" }}
            >
              {accept.isPending ? "Accepting…" : "Accept"}
            </button>
          </div>
          <p className="text-xs mt-2" style={{ color: "var(--brand-on-surface-variant)" }}>
            Released{" "}
            {task.poolReleasedAt
              ? new Date(task.poolReleasedAt).toLocaleString("en-NG", { dateStyle: "medium", timeStyle: "short" })
              : "—"}
          </p>
        </div>
      ))}
    </div>
  );
}

export default function AvailableJobsList({ roles }: Props) {
  const [activeRole, setActiveRole] = useState<TaskRole>(roles[0]);

  if (roles.length === 1) {
    return <JobList role={roles[0]} />;
  }

  return (
    <div>
      <div className="flex gap-1 mb-4 border-b" style={{ borderColor: "rgba(196,198,207,0.2)" }}>
        {roles.map((role) => {
          const isActive = role === activeRole;
          const chip = ROLE_COLORS[role];
          return (
            <button
              key={role}
              onClick={() => setActiveRole(role)}
              className="px-3 py-2 text-xs font-semibold border-b-2 transition-colors -mb-px"
              style={{
                borderBottomColor: isActive ? chip.color : "transparent",
                color: isActive ? chip.color : "var(--brand-on-surface-variant)",
                cursor: "pointer",
              }}
            >
              {ROLE_LABELS[role]}
            </button>
          );
        })}
      </div>
      <JobList role={activeRole} />
    </div>
  );
}
