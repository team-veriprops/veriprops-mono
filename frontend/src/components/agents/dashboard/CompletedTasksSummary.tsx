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
    <div
      className="rounded-xl p-4 space-y-3"
      style={{ backgroundColor: "#fff", border: "1px solid rgba(196,198,207,0.2)" }}
    >
      <div className="flex items-center gap-2">
        <CheckCircle2 className="h-4 w-4" style={{ color: "var(--brand-viridian)" }} />
        <h3 className="text-sm font-semibold" style={{ color: "var(--brand-navy)" }}>Completed</h3>
      </div>
      {isLoading ? (
        <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
      ) : (
        <div className="flex gap-6">
          <div>
            <p className="text-2xl font-bold" style={{ color: "var(--brand-viridian)" }}>{approved}</p>
            <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>Approved</p>
          </div>
          <div>
            <p className="text-2xl font-bold" style={{ color: "#2563eb" }}>{submitted}</p>
            <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>Under Review</p>
          </div>
          <div>
            <p className="text-2xl font-bold" style={{ color: "var(--brand-navy)" }}>{tasks.length}</p>
            <p className="text-xs" style={{ color: "var(--brand-on-surface-variant)" }}>Total</p>
          </div>
        </div>
      )}
    </div>
  );
}
