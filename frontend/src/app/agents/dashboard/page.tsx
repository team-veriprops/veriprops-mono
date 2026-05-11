"use client";

import { useAgentApplication } from "@components/agents/libs/useAgentApplicationQueries";
import AvailableJobsList from "@components/agents/dashboard/AvailableJobsList";
import ActiveTasksList from "@components/agents/dashboard/ActiveTasksList";
import CompletedTasksSummary from "@components/agents/dashboard/CompletedTasksSummary";
import type { TaskRole } from "@components/agents/libs/agent-service";

export default function AgentDashboardPage() {
  const { data: app } = useAgentApplication();
  const roles: TaskRole[] = (app?.types ?? []) as TaskRole[];
  const primaryRole: TaskRole = roles[0] ?? "FIELD";

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-gray-900">Agent Dashboard</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Manage your tasks and track your progress.
        </p>
      </div>

      <CompletedTasksSummary />

      {/* Active tasks */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3">My Active Tasks</h2>
        <ActiveTasksList />
      </section>

      {/* Available jobs */}
      <section>
        <h2 className="text-base font-semibold text-gray-800 mb-3">
          Available Jobs
          {primaryRole && (
            <span className="ml-2 text-xs font-normal text-gray-500">
              ({primaryRole})
            </span>
          )}
        </h2>
        {roles.length === 0 ? (
          <p className="text-sm text-gray-400">
            Your agent application has not been approved yet.
          </p>
        ) : (
          <AvailableJobsList role={primaryRole} />
        )}
      </section>
    </div>
  );
}
