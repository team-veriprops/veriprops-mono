"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Briefcase, CheckCircle2, Clock } from "lucide-react";
import { useActiveTasks, useCompletedTasks } from "@components/agents/libs/useAgentTaskQueries";
import type { Task, TaskRole, TaskStatus } from "@components/agents/libs/agent-service";
import { ROUTES } from "@lib/routes";

type Tab = "active" | "completed";

const ROLE_COLORS: Record<TaskRole, { color: string; bg: string }> = {
  FIELD:    { color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
  SURVEYOR: { color: "#2563eb", bg: "rgba(37,99,235,0.08)" },
  REGISTRY: { color: "#7c3aed", bg: "rgba(124,58,237,0.08)" },
  LAWYER:   { color: "#d97706", bg: "rgba(245,158,11,0.08)" },
};

const STATUS_CONFIG: Partial<Record<TaskStatus, { label: string; color: string; bg: string }>> = {
  ACCEPTED:    { label: "Accepted",    color: "#d97706", bg: "rgba(245,158,11,0.1)" },
  IN_PROGRESS: { label: "In Progress", color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
  SUBMITTED:   { label: "Under Review",color: "#2563eb", bg: "rgba(37,99,235,0.08)" },
  APPROVED:    { label: "Approved",    color: "#3f6653", bg: "rgba(63,102,83,0.1)" },
  REJECTED:    { label: "Rejected",    color: "#ef4444", bg: "rgba(239,68,68,0.08)" },
};

function TaskRow({ task }: { task: Task }) {
  const router = useRouter();
  const role = task.role as TaskRole;
  const roleChip = ROLE_COLORS[role] ?? { color: "#6b7280", bg: "#f3f4f6" };
  const statusChip = STATUS_CONFIG[task.status as TaskStatus] ?? {
    label: task.status,
    color: "#6b7280",
    bg: "#f3f4f6",
  };

  const dateLabel =
    task.submittedAt
      ? `Submitted ${new Date(task.submittedAt).toLocaleDateString("en-NG", { dateStyle: "medium" })}`
      : task.acceptedAt
      ? `Accepted ${new Date(task.acceptedAt).toLocaleDateString("en-NG", { dateStyle: "medium" })}`
      : `Created ${new Date(task.dateCreated).toLocaleDateString("en-NG", { dateStyle: "medium" })}`;

  return (
    <div
      onClick={() => router.push(ROUTES.AGENT.TASK_DETAIL(task.id))}
      className="flex items-center justify-between rounded-xl border px-4 py-3 transition-all hover:shadow-sm"
      style={{ backgroundColor: "#fff", borderColor: "rgba(196,198,207,0.2)", cursor: "pointer" }}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className="px-2 py-0.5 rounded-full text-xs font-semibold shrink-0"
            style={{ color: roleChip.color, backgroundColor: roleChip.bg }}
          >
            {role}
          </span>
          <span className="text-sm font-medium truncate" style={{ color: "var(--brand-navy)" }}>
            {role} Verification
          </span>
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs font-mono" style={{ color: "var(--brand-on-surface-variant)" }}>
            {task.verificationId.slice(0, 10)}…
          </span>
          <span className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>
            · {dateLabel}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0 ml-3">
        <span
          className="text-xs font-semibold px-2.5 py-0.5 rounded-full"
          style={{ color: statusChip.color, backgroundColor: statusChip.bg }}
        >
          {statusChip.label}
        </span>
        <span className="text-xs font-medium" style={{ color: "var(--brand-viridian)" }}>
          View →
        </span>
      </div>
    </div>
  );
}

function ActiveTab() {
  const { data, isLoading } = useActiveTasks();
  const tasks: Task[] = (data as any)?.data ?? [];

  if (isLoading) {
    return <div className="py-10 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>;
  }

  if (tasks.length === 0) {
    return (
      <div className="py-12 text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        <Clock className="h-8 w-8 mx-auto mb-2 opacity-30" />
        <p className="text-sm">No active tasks.</p>
        <p className="text-xs mt-1 opacity-70">Accept a job from the dashboard to get started.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => <TaskRow key={task.id} task={task} />)}
    </div>
  );
}

function CompletedTab() {
  const { data, isLoading } = useCompletedTasks();
  const tasks: Task[] = (data as any)?.data ?? [];

  if (isLoading) {
    return <div className="py-10 text-center text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</div>;
  }

  if (tasks.length === 0) {
    return (
      <div className="py-12 text-center" style={{ color: "var(--brand-on-surface-variant)" }}>
        <CheckCircle2 className="h-8 w-8 mx-auto mb-2 opacity-30" />
        <p className="text-sm">No completed tasks yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {tasks.map((task) => <TaskRow key={task.id} task={task} />)}
    </div>
  );
}

const TABS: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "active",    label: "Active",    icon: Clock },
  { id: "completed", label: "Completed", icon: CheckCircle2 },
];

export default function AgentTasksPage() {
  const [tab, setTab] = useState<Tab>("active");

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>
          My Tasks
        </h1>
        <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
          All tasks assigned to you, past and present.
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b" style={{ borderColor: "rgba(196,198,207,0.2)" }}>
        {TABS.map(({ id, label, icon: Icon }) => {
          const isActive = tab === id;
          return (
            <button
              key={id}
              onClick={() => setTab(id)}
              className="flex items-center gap-1.5 px-4 py-2.5 text-sm font-semibold border-b-2 -mb-px transition-colors"
              style={{
                borderBottomColor: isActive ? "var(--brand-viridian)" : "transparent",
                color: isActive ? "var(--brand-viridian)" : "var(--brand-on-surface-variant)",
                cursor: "pointer",
              }}
            >
              <Icon className="w-4 h-4" />
              {label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      {tab === "active"    && <ActiveTab />}
      {tab === "completed" && <CompletedTab />}
    </div>
  );
}
