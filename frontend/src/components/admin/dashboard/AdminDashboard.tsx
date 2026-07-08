"use client";

import Link from "next/link";
import {
  AlertTriangle, BarChart3, ChevronRight, ClipboardList, Clock, CreditCard,
  DollarSign, Inbox, UserRoundCheck, Users,
} from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatCard } from "@components/ui/StatCard";
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
    <div className="mx-auto w-full max-w-5xl space-y-6 p-4 sm:p-6" data-testid="admin-dashboard">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-foreground">Mission Control</h1>
        <Link
          href={ROUTES.ADMIN.ANALYTICS}
          className="inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline"
        >
          <BarChart3 className="size-4" /> Analytics
        </Link>
      </div>

      <AsyncStateComponent<AdminDashboardData>
        isLoading={isLoading}
        isError={isError}
        data={data}
      >
        {(summary) => (
          <div className="space-y-6">
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
                      <Link href={ROUTES.ADMIN.VERIFICATION_DETAIL(v.id)}>
                        <Card className="flex items-center justify-between gap-3 p-4 transition hover:border-primary">
                          <div className="min-w-0 space-y-1">
                            <p className="truncate font-medium">{v.vid}</p>
                            <p className="text-xs text-muted-foreground">
                              {v.stateRegion ?? "—"}{v.tier ? ` · ${humanizeEnumLabel(v.tier)}` : ""}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            {v.slaHealth === SlaHealth.OVERDUE ? (
                              <span className="text-xs font-medium text-red-600 dark:text-red-400">Overdue</span>
                            ) : null}
                            <VerificationStatusBadge status={v.status} />
                            <ChevronRight className="size-4 text-muted-foreground" />
                          </div>
                        </Card>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </AsyncStateComponent>
    </div>
  );
}
