"use client";

import { useAgentApplication } from "@components/agents/libs/useAgentApplicationQueries";
import AvailableJobsList from "@components/agents/dashboard/AvailableJobsList";
import ActiveTasksList from "@components/agents/dashboard/ActiveTasksList";
import CompletedTasksSummary from "@components/agents/dashboard/CompletedTasksSummary";
import AgentKpiBar from "@components/agents/dashboard/AgentKpiBar";
import AvailabilityToggle from "@components/agents/dashboard/AvailabilityToggle";
import type { TaskRole } from "@components/agents/libs/agent-service";

export default function AgentDashboardPage() {
  const { data: app, isLoading: appLoading } = useAgentApplication();
  const roles: TaskRole[] = (app?.types ?? []) as TaskRole[];

  return (
    <div className="p-6 space-y-8">
      {/* Header row with availability toggle */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold" style={{ color: "var(--brand-navy)" }}>
            Agent Dashboard
          </h1>
          <p className="text-sm mt-0.5" style={{ color: "var(--brand-on-surface-variant)" }}>
            Manage your tasks and track your progress.
          </p>
        </div>
        <AvailabilityToggle />
      </div>

      {/* KPI bar: total jobs · accuracy · timeliness · available earnings */}
      <AgentKpiBar />

      {/* Active tasks */}
      <section>
        <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
          My Active Tasks
        </h2>
        <ActiveTasksList />
      </section>

      {/* Available jobs — filtered by all approved roles */}
      <section>
        <h2 className="text-base font-semibold mb-3" style={{ color: "var(--brand-navy)" }}>
          Available Jobs
        </h2>
        {appLoading ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>Loading…</p>
        ) : roles.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--brand-on-surface-variant)" }}>
            Your agent application has not been approved yet.
          </p>
        ) : (
          <AvailableJobsList roles={roles} />
        )}
      </section>

      {/* Completed summary */}
      <CompletedTasksSummary />
    </div>
  );
}
