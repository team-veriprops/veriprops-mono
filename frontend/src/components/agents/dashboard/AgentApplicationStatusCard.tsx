"use client";

import { Badge } from "@3rdparty/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { AgentApplicationStatus } from "@/types/agent";
import { useAgentStatusQuery } from "@components/agents/libs/useAgentQueries";

const STATUS_BADGE: Record<AgentApplicationStatus, { label: string; variant: "default" | "secondary" | "destructive" }> = {
  [AgentApplicationStatus.PENDING]: { label: "Pending review", variant: "secondary" },
  [AgentApplicationStatus.APPROVED]: { label: "Approved", variant: "default" },
  [AgentApplicationStatus.REJECTED]: { label: "Rejected", variant: "destructive" },
};

/**
 * PRD §3.1 Approval Status Dashboard. Only ever mounts for PENDING/APPROVED —
 * the `/agents` layout's compulsory onboarding gate forces "no application" and
 * REJECTED agents into the onboarding wizard before this card can render.
 */
export default function AgentApplicationStatusCard() {
  const { data: status, isLoading } = useAgentStatusQuery();

  if (isLoading || !status) {
    return <div className="text-muted-foreground" data-testid="agent-status-loading">Loading…</div>;
  }

  const badge = STATUS_BADGE[status.status];

  return (
    <Card data-testid="agent-status-card">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Agent application</CardTitle>
        <Badge variant={badge.variant}>{badge.label}</Badge>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex justify-between gap-4">
          <span className="text-muted-foreground">Applied for</span>
          <span className="font-medium">{status.roles.join(", ")}</span>
        </div>
        {status.status === AgentApplicationStatus.APPROVED && (
          <div className="flex justify-between gap-4">
            <span className="text-muted-foreground">Active roles</span>
            <span className="font-medium">{status.activeRoles.join(", ") || "—"}</span>
          </div>
        )}
        {status.status === AgentApplicationStatus.PENDING && (
          <p className="text-muted-foreground">
            Your application is under review. Pending applications don&apos;t receive jobs yet.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
