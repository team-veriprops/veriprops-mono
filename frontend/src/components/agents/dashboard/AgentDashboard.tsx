"use client";

import Link from "next/link";
import { CheckCircle2, ClipboardList, Inbox, Send, Star, TrendingUp } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { StatCard } from "@components/ui/StatCard";
import AgentApplicationStatusCard from "@components/agents/dashboard/AgentApplicationStatusCard";
import { AvailabilityToggle } from "@components/agents/reputation/AvailabilityToggle";
import { useAgentProfileQuery } from "@components/agents/reputation/libs/useReputationQueries";
import { useAgentStatusQuery } from "@components/agents/libs/useAgentQueries";
import { useAgentDashboardQuery } from "@components/agents/tasks/libs/useAgentTaskQueries";
import { ROUTES } from "@lib/routes";
import { AgentApplicationStatus } from "@/types/agent";

/**
 * Agent home (§7). The approval-status card plus, once approved, a backend-derived
 * snapshot of the agent's own workload (`/agents/tasks/summary`).
 */
export default function AgentDashboard() {
  const { data: status } = useAgentStatusQuery();
  const approved = status?.status === AgentApplicationStatus.APPROVED;
  const { data: summary } = useAgentDashboardQuery(approved);
  const { data: profile } = useAgentProfileQuery();

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-4 sm:p-6" data-testid="agent-dashboard">
      <h1 className="text-2xl font-bold text-foreground">Agent</h1>
      <AgentApplicationStatusCard />

      {approved && summary ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Your tasks</h2>
            <Link href={ROUTES.AGENT.TASKS} className="text-xs font-medium text-primary hover:underline">
              View tasks
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="To accept" value={summary.assigned} icon={Inbox} tone="warning" href={ROUTES.AGENT.TASKS} />
            <StatCard label="In hand" value={summary.active} icon={ClipboardList} href={ROUTES.AGENT.TASKS} />
            <StatCard label="Submitted" value={summary.submitted} icon={Send} />
            <StatCard label="Approved" value={summary.approved} icon={CheckCircle2} tone="success" />
          </div>
        </section>
      ) : null}

      {approved && profile ? (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">Reputation &amp; availability</h2>
            <Link href={ROUTES.AGENT.PROFILE} className="text-xs font-medium text-primary hover:underline">
              View profile
            </Link>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Accuracy" value={`${profile.metrics.accuracyScore.toFixed(1)} / 5`} icon={Star} tone="success" />
            <StatCard label="Reputation" value={profile.metrics.compositeScore} icon={TrendingUp} />
            <StatCard label="Completion" value={`${profile.metrics.completionRate}%`} icon={CheckCircle2} />
            <StatCard label="Jobs done" value={profile.metrics.completedJobs} icon={ClipboardList} />
          </div>
          <Card className="p-4">
            <AvailabilityToggle
              value={profile.availability}
              effective={profile.effectiveAvailability}
              atCapacity={profile.activeTaskCount >= profile.maxActiveTasks}
            />
          </Card>
        </section>
      ) : null}
    </div>
  );
}
