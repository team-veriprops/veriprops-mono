"use client";

import Link from "next/link";
import { ArrowUpRight, CreditCard, HandCoins, Receipt } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { PageShell } from "@components/ui/PageShell";
import { AttentionChip } from "@components/ui/AttentionChip";
import { MiniBarBreakdown } from "@components/ui/MiniBarBreakdown";
import { useFinanceSummaryQuery } from "./libs/useFinanceSummaryQuery";
import { FinanceSummary } from "@/types/finance";
import { ROUTES } from "@lib/routes";
import { formatMinor } from "@lib/utils";

/**
 * Finance landing (§18.1) — collected revenue + payment/commission/payout health, linking
 * into the detailed panels (Payouts approve/hold/adjust lives in its own page). Backend-derived.
 */
export default function AdminFinance() {
  const { data, isLoading, isError } = useFinanceSummaryQuery();

  return (
    <AsyncStateComponent<FinanceSummary> isLoading={isLoading} isError={isError} data={data}>
      {(summary) => (
        <PageShell
          title="Finance"
          description="Collected revenue and payment, commission, and payout health."
          data-testid="admin-finance"
          meta={
            summary.pendingPayouts > 0 ? (
              <AttentionChip icon={HandCoins} tone="warning" href={ROUTES.ADMIN.FINANCE_PAYOUTS}>
                {summary.pendingPayouts} payout{summary.pendingPayouts === 1 ? "" : "s"} pending
              </AttentionChip>
            ) : undefined
          }
        >
          {/* Hero: collected revenue is the single headline figure. */}
          <Card className="p-6">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Collected revenue</p>
            <p className="mt-1 text-4xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
              {formatMinor(summary.revenueMinor) ?? "—"}
            </p>
          </Card>

          <div className="grid gap-4 lg:grid-cols-3">
            <BreakdownCard title="Payments" icon={<CreditCard className="size-4" />} counts={summary.paymentsByStatus} />
            <BreakdownCard title="Commissions" icon={<Receipt className="size-4" />} counts={summary.commissionsByStatus} />
            <BreakdownCard
              title="Payouts"
              icon={<HandCoins className="size-4" />}
              counts={summary.payoutsByStatus}
              href={ROUTES.ADMIN.FINANCE_PAYOUTS}
            />
          </div>
        </PageShell>
      )}
    </AsyncStateComponent>
  );
}

function BreakdownCard({
  title, counts, icon, href,
}: { title: string; counts: Record<string, number>; icon: React.ReactNode; href?: string }) {
  const heading = (
    <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
      {icon} {title}
      {href ? <ArrowUpRight className="ml-auto size-4 text-muted-foreground" aria-hidden /> : null}
    </div>
  );
  return (
    <Card className="space-y-3 p-4">
      {href ? (
        <Link href={href} className="block transition-colors hover:text-primary">
          {heading}
        </Link>
      ) : (
        heading
      )}
      <MiniBarBreakdown counts={counts} />
    </Card>
  );
}
