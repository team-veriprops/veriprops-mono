"use client";

import Link from "next/link";
import { ChevronRight, ClipboardList, CreditCard, FileCheck2, Gift, Plus, ShieldCheck } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatCard } from "@components/ui/StatCard";
import { VerificationStatusBadge } from "@components/portal/verifications/VerificationStatusBadge";
import { useCustomerDashboardQuery } from "@components/portal/libs/useVerificationQueries";
import { useReferralSummaryQuery } from "@components/portal/referrals/libs/useReferralQueries";
import { ROUTES } from "@lib/routes";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { CustomerDashboard, ResumableDraft } from "@/types/tracking";

/**
 * Portal home (§9). A quick-glance summary of the customer's verifications — every
 * count is backend-derived (`/verifications/summary`) — plus their most recent items.
 */
export default function PortalDashboard() {
  const { data, isLoading, isError } = useCustomerDashboardQuery();
  const { data: referral } = useReferralSummaryQuery();

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
            {summary.resumableDraft && <RecoveryBanner draft={summary.resumableDraft} />}

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatCard label="Total" value={summary.total} icon={ClipboardList} href={ROUTES.PORTAL.VERIFICATIONS} />
              <StatCard label="In progress" value={summary.inProgress} icon={FileCheck2} tone="warning" />
              <StatCard label="Awaiting payment" value={summary.awaitingPayment} icon={CreditCard} />
              <StatCard label="Completed" value={summary.completed} icon={ShieldCheck} tone="success" />
            </div>

            {referral && (referral.availableCreditMinor > 0 || referral.pendingCreditMinor > 0) && (
              <StatCard
                label="Referral credit"
                value={formatMinor(referral.availableCreditMinor) ?? "—"}
                icon={Gift}
                tone="success"
                href={ROUTES.PORTAL.REFERRALS}
                hint={referral.pendingCreditMinor > 0 ? `${formatMinor(referral.pendingCreditMinor)} pending` : undefined}
              />
            )}

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
                              {v.vid}{v.tier ? ` · ${humanizeEnumLabel(v.tier)}` : ""}
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

/**
 * Abandonment-recovery banner (§17.1): a saved but incomplete verification can be
 * resumed exactly where the customer left off — at payment, or in the wizard.
 */
function RecoveryBanner({ draft }: { draft: ResumableDraft }) {
  const href = draft.needsPayment
    ? ROUTES.PORTAL.VERIFICATION_PAY(draft.id)
    : ROUTES.PORTAL.VERIFICATIONS_NEW;
  return (
    <Card
      className="flex flex-col gap-3 border-amber-500/40 bg-amber-500/5 p-4 sm:flex-row sm:items-center sm:justify-between"
      data-testid="portal-recovery-banner"
    >
      <div className="min-w-0 space-y-1">
        <p className="font-medium text-foreground">Pick up where you left off</p>
        <p className="text-sm text-muted-foreground">
          Your verification {draft.vid} is saved and ready to complete.
        </p>
      </div>
      <Button asChild size="sm">
        <Link href={href}>{draft.needsPayment ? "Complete payment" : "Resume"}</Link>
      </Button>
    </Card>
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
