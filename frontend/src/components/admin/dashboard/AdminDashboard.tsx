"use client";

import Link from "next/link";
import {
  AlertTriangle, BarChart3, ClipboardList, Clock, CreditCard,
  DollarSign, Inbox, UserRoundCheck, Users,
} from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatCard } from "@components/ui/StatCard";
import { PageShell } from "@components/ui/PageShell";
import { LinkCardRow } from "@components/ui/LinkCardRow";
import { AttentionChip } from "@components/ui/AttentionChip";
import { VerificationStatusBadge } from "@components/portal/verifications/VerificationStatusBadge";
import { useAdminDashboardQuery } from "@components/admin/verifications/libs/useAdminVerificationQueries";
import { ROUTES } from "@lib/routes";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { AdminDashboard as AdminDashboardData, SlaHealth } from "@/types/adminVerification";

/**
 * Admin operations home (§6). Backend-owned queue health (`/admin/verifications/summary`):
 * status rollups, overdue/unassigned counts, pending applications, open chargebacks, and
 * the most recent verifications. No figure is derived on the client.
 */
export default function AdminDashboard() {
  const { data, isLoading, isError } = useAdminDashboardQuery();

  return (
    <PageShell
      title="Mission Control"
      description="Live business and queue health."
      width="wide"
      data-testid="admin-dashboard"
      actions={
        <Link
          href={ROUTES.ADMIN.ANALYTICS}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <BarChart3 className="size-4" /> Analytics
        </Link>
      }
    >
      <AsyncStateComponent<AdminDashboardData>
        isLoading={isLoading}
        isError={isError}
        data={data}
      >
        {(summary) => (
          <div className="space-y-6">
            {/* Urgent operational signals — surfaced up top, each linking to its queue. */}
            {(summary.overdue > 0 || summary.slaAtRisk > 0 || summary.openChargebacks > 0 || summary.unassignedPoolTasks > 0) && (
              <div className="flex flex-wrap gap-2">
                {summary.overdue > 0 && (
                  <AttentionChip icon={AlertTriangle} tone="danger" href={ROUTES.ADMIN.VERIFICATIONS}>
                    {summary.overdue} overdue
                  </AttentionChip>
                )}
                {summary.slaAtRisk > 0 && (
                  <AttentionChip icon={Clock} tone="warning" href={ROUTES.ADMIN.VERIFICATIONS}>
                    {summary.slaAtRisk} SLA at risk
                  </AttentionChip>
                )}
                {summary.unassignedPoolTasks > 0 && (
                  <AttentionChip icon={Inbox} tone="warning" href={ROUTES.ADMIN.VERIFICATIONS}>
                    {summary.unassignedPoolTasks} unassigned
                  </AttentionChip>
                )}
                {summary.openChargebacks > 0 && (
                  <AttentionChip icon={CreditCard} tone="danger" href={ROUTES.ADMIN.FINANCE}>
                    {summary.openChargebacks} open chargebacks
                  </AttentionChip>
                )}
              </div>
            )}

            {/* Mission Control: live business + queue health (§18.1). */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              <StatCard label="Revenue" value={formatMinor(summary.revenueMinor) ?? "—"} icon={DollarSign} tone="success" href={ROUTES.ADMIN.FINANCE} />
              <StatCard label="Verifications" value={summary.total} icon={ClipboardList} href={ROUTES.ADMIN.VERIFICATIONS} />
              <StatCard label="Available agents" value={summary.availableAgents} icon={Users} tone="success" />
              <StatCard label="SLA at risk" value={summary.slaAtRisk} icon={Clock} tone={summary.slaAtRisk > 0 ? "warning" : "default"} />
              <StatCard label="Overdue" value={summary.overdue} icon={AlertTriangle} tone={summary.overdue > 0 ? "danger" : "default"} />
              <StatCard label="Unassigned tasks" value={summary.unassignedPoolTasks} icon={Inbox} tone="warning" />
              <StatCard label="Pending applications" value={summary.pendingAgentApplications} icon={UserRoundCheck} href={ROUTES.ADMIN.AGENT_APPLICATIONS} />
              <StatCard label="Open chargebacks" value={summary.openChargebacks} icon={CreditCard} tone={summary.openChargebacks > 0 ? "danger" : "default"} />
            </div>

            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-foreground">Recent verifications</h2>
                <Link
                  href={ROUTES.ADMIN.VERIFICATIONS}
                  className="text-xs font-medium text-primary hover:underline"
                >
                  Open queue
                </Link>
              </div>

              {summary.recent.length === 0 ? (
                <Card className="p-6 text-center text-sm text-muted-foreground">
                  No verifications yet.
                </Card>
              ) : (
                <ul className="space-y-2">
                  {summary.recent.map((v) => (
                    <li key={v.id}>
                      <LinkCardRow
                        href={ROUTES.ADMIN.VERIFICATION_DETAIL(v.id)}
                        title={v.vid}
                        subtitle={`${v.stateRegion ?? "—"}${v.tier ? ` · ${humanizeEnumLabel(v.tier)}` : ""}`}
                        trailing={
                          <>
                            {v.slaHealth === SlaHealth.OVERDUE ? (
                              <span className="text-xs font-medium text-red-600 dark:text-red-400">Overdue</span>
                            ) : null}
                            <VerificationStatusBadge status={v.status} />
                          </>
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </AsyncStateComponent>
    </PageShell>
  );
}
