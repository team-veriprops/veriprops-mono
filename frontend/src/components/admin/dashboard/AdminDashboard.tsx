"use client";

import Link from "next/link";
import { AlertTriangle, ChevronRight, ClipboardList, CreditCard, Inbox, UserRoundCheck } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatCard } from "@components/ui/StatCard";
import { VerificationStatusBadge } from "@components/portal/verifications/VerificationStatusBadge";
import { useAdminDashboardQuery } from "@components/admin/verifications/libs/useAdminVerificationQueries";
import { ROUTES } from "@lib/routes";
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
      <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>

      <AsyncStateComponent<AdminDashboardData>
        isLoading={isLoading}
        isError={isError}
        data={data}
      >
        {(summary) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <StatCard
                label="Verifications"
                value={summary.total}
                icon={ClipboardList}
                href={ROUTES.ADMIN.VERIFICATIONS}
              />
              <StatCard
                label="Overdue"
                value={summary.overdue}
                icon={AlertTriangle}
                tone={summary.overdue > 0 ? "danger" : "default"}
              />
              <StatCard label="Unassigned tasks" value={summary.unassignedPoolTasks} icon={Inbox} tone="warning" />
              <StatCard
                label="Pending applications"
                value={summary.pendingAgentApplications}
                icon={UserRoundCheck}
                href={ROUTES.ADMIN.AGENT_APPLICATIONS}
              />
              <StatCard
                label="Open chargebacks"
                value={summary.openChargebacks}
                icon={CreditCard}
                tone={summary.openChargebacks > 0 ? "danger" : "default"}
              />
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
                              {v.stateRegion ?? "—"}{v.tier ? ` · ${v.tier}` : ""}
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
