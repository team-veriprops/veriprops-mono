"use client";

import Link from "next/link";
import { ChevronRight, ClipboardList, CreditCard, FileCheck2, Plus, ShieldCheck } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatCard } from "@components/ui/StatCard";
import { VerificationStatusBadge } from "@components/portal/verifications/VerificationStatusBadge";
import { useCustomerDashboardQuery } from "@components/portal/libs/useVerificationQueries";
import { ROUTES } from "@lib/routes";
import { CustomerDashboard } from "@/types/tracking";

/**
 * Portal home (§9). A quick-glance summary of the customer's verifications — every
 * count is backend-derived (`/verifications/summary`) — plus their most recent items.
 */
export default function PortalDashboard() {
  const { data, isLoading, isError } = useCustomerDashboardQuery();

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6" data-testid="portal-dashboard">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-foreground">Dashboard</h1>
        <Button asChild size="sm">
          <Link href={ROUTES.PORTAL.VERIFICATIONS_NEW}>
            <Plus className="size-4" /> New Verification
          </Link>
        </Button>
      </div>

      <AsyncStateComponent<CustomerDashboard>
        isLoading={isLoading}
        isError={isError}
        data={data}
      >
        {(summary) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Total" value={summary.total} icon={ClipboardList} href={ROUTES.PORTAL.VERIFICATIONS} />
              <StatCard label="In progress" value={summary.inProgress} icon={FileCheck2} tone="warning" />
              <StatCard label="Awaiting payment" value={summary.awaitingPayment} icon={CreditCard} />
              <StatCard label="Completed" value={summary.completed} icon={ShieldCheck} tone="success" />
            </div>

            <section className="space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-foreground">Recent verifications</h2>
                <Link
                  href={ROUTES.PORTAL.VERIFICATIONS}
                  className="text-xs font-medium text-primary hover:underline"
                >
                  View all
                </Link>
              </div>

              {summary.recent.length === 0 ? (
                <EmptyState />
              ) : (
                <ul className="space-y-2">
                  {summary.recent.map((v) => (
                    <li key={v.id}>
                      <Link href={ROUTES.PORTAL.VERIFICATION_TRACKING(v.id)}>
                        <Card className="flex items-center justify-between gap-3 p-4 transition hover:border-primary">
                          <div className="min-w-0 space-y-1">
                            <p className="truncate font-medium">{v.address ?? v.vid}</p>
                            <p className="text-xs text-muted-foreground">
                              {v.vid}{v.tier ? ` · ${v.tier}` : ""}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <VerificationStatusBadge status={v.status} label={v.statusLabel} />
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

function EmptyState() {
  return (
    <Card className="flex flex-col items-center gap-3 p-8 text-center">
      <p className="text-sm text-muted-foreground">
        Start your first property verification to see it tracked live here.
      </p>
      <Button asChild>
        <Link href={ROUTES.PORTAL.VERIFICATIONS_NEW}>Start a verification</Link>
      </Button>
    </Card>
  );
}
