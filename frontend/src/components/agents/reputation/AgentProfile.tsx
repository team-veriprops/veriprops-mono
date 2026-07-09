"use client";

import Link from "next/link";
import { Award, CheckCircle2, Clock, Star } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { StatCard } from "@components/ui/StatCard";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { ROUTES } from "@/lib/routes";
import { AgentProfileSummary } from "@/types/agentReputation";
import { AvailabilityToggle } from "./AvailabilityToggle";
import { useAgentProfileQuery } from "./libs/useReputationQueries";

/** Agent profile (§16.1): reputation metrics, availability, coverage summary, active-since. */
export default function AgentProfile() {
  const { data, isLoading, isError } = useAgentProfileQuery();

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-4 sm:p-6">
      <h1 className="text-lg font-semibold">My profile</h1>
      <AsyncStateComponent<AgentProfileSummary>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading profile…"
      >
        {(p) => (
          <>
            <Card className="space-y-3 p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Availability</h2>
                <span className="text-xs text-muted-foreground">
                  {p.activeTaskCount}/{p.maxActiveTasks} active tasks
                </span>
              </div>
              <AvailabilityToggle
                value={p.availability}
                effective={p.effectiveAvailability}
                atCapacity={p.activeTaskCount >= p.maxActiveTasks}
              />
            </Card>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatCard label="Accuracy" value={`${p.metrics.accuracyScore.toFixed(1)} / 5`} icon={Star} tone="success" />
              <StatCard label="Completion" value={`${p.metrics.completionRate}%`} icon={CheckCircle2} />
              <StatCard label="Timeliness" value={`${p.metrics.timelinessRate}%`} icon={Clock} />
              <StatCard label="Jobs done" value={p.metrics.completedJobs} icon={Award} hint={`${p.metrics.totalJobs} total`} />
            </div>

            <Card className="space-y-3 p-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold">Coverage</h2>
                <Button asChild variant="outline" size="sm">
                  <Link href={ROUTES.AGENT.SETTINGS_COVERAGE}>Edit coverage</Link>
                </Button>
              </div>
              {p.coverage.length === 0 ? (
                <p className="text-sm text-muted-foreground">No coverage set yet.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {p.coverage.map((c) => (
                    <span key={c.state} className="rounded-full bg-muted px-2 py-1 text-xs capitalize">
                      {c.state.replace(/-/g, " ")}
                    </span>
                  ))}
                </div>
              )}
              {p.coverageFlaggedForReview && (
                <p className="text-xs text-amber-600 dark:text-amber-400">
                  Your coverage is unusually wide and is flagged for admin review.
                </p>
              )}
            </Card>
          </>
        )}
      </AsyncStateComponent>
    </div>
  );
}
