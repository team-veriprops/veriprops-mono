"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@3rdparty/ui/button";
import { Badge } from "@3rdparty/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@3rdparty/ui/card";
import { ROUTES } from "@lib/routes";
import { AgentApplicationStatus } from "@/types/agent";
import { useAgentStatusQuery } from "@components/agents/libs/useAgentQueries";

const STATUS_BADGE: Record<AgentApplicationStatus, { label: string; variant: "default" | "secondary" | "destructive" }> = {
  [AgentApplicationStatus.PENDING]: { label: "Pending review", variant: "secondary" },
  [AgentApplicationStatus.APPROVED]: { label: "Approved", variant: "default" },
  [AgentApplicationStatus.REJECTED]: { label: "Rejected", variant: "destructive" },
};

/**
 * PRD §3.1 Approval Status Dashboard — the agent's landing view. Prompts an
 * application when none exists; otherwise shows Pending / Approved / Rejected.
 */
export default function AgentApplicationStatusCard() {
  const router = useRouter();
  const { data: status, isLoading } = useAgentStatusQuery();

  if (isLoading) {
    return <div className="text-muted-foreground" data-testid="agent-status-loading">Loading…</div>;
  }

  if (!status) {
    return (
      <Card data-testid="agent-status-empty">
        <CardHeader>
          <CardTitle>Become a Verified Agent</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Apply to carry out verifications as a Field Agent, Surveyor, Registry Agent, or Lawyer.
          </p>
          <Button onClick={() => router.push(ROUTES.AGENT.APPLY)} data-testid="agent-apply-cta">
            Start application
          </Button>
        </CardContent>
      </Card>
    );
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
        {status.status === AgentApplicationStatus.REJECTED && status.rejectionReason && (
          <p className="text-destructive">Reason: {status.rejectionReason}</p>
        )}
        {status.status === AgentApplicationStatus.PENDING && (
          <p className="text-muted-foreground">
            Your application is under review. Pending applications don&apos;t receive jobs yet.
          </p>
        )}
        {status.status === AgentApplicationStatus.REJECTED && (
          <Link href={ROUTES.AGENT.APPLY} className="text-primary underline">
            Re-apply
          </Link>
        )}
      </CardContent>
    </Card>
  );
}
