"use client";

import Link from "next/link";
import { CreditCard, DollarSign, HandCoins, Receipt } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { StatCard } from "@components/ui/StatCard";
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
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6" data-testid="admin-finance">
      <h1 className="text-2xl font-bold text-foreground">Finance</h1>

      <AsyncStateComponent<FinanceSummary> isLoading={isLoading} isError={isError} data={data}>
        {(summary) => (
          <div className="space-y-6">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <StatCard label="Revenue" value={formatMinor(summary.revenueMinor) ?? "—"} icon={DollarSign} tone="success" />
              <StatCard label="Pending payouts" value={summary.pendingPayouts} icon={HandCoins} tone={summary.pendingPayouts > 0 ? "warning" : "default"} href={ROUTES.ADMIN.FINANCE_PAYOUTS} />
              <StatCard label="Payments" value={sum(summary.paymentsByStatus)} icon={CreditCard} />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <StatusBreakdown title="Payments" counts={summary.paymentsByStatus} icon={<CreditCard className="size-4" />} />
              <StatusBreakdown title="Commissions" counts={summary.commissionsByStatus} icon={<Receipt className="size-4" />} />
              <StatusBreakdown title="Payouts" counts={summary.payoutsByStatus} icon={<HandCoins className="size-4" />} href={ROUTES.ADMIN.FINANCE_PAYOUTS} />
            </div>
          </div>
        )}
      </AsyncStateComponent>
    </div>
  );
}

function sum(counts: Record<string, number>): number {
  return Object.values(counts).reduce((a, b) => a + b, 0);
}

function StatusBreakdown({
  title, counts, icon, href,
}: { title: string; counts: Record<string, number>; icon: React.ReactNode; href?: string }) {
  const entries = Object.entries(counts);
  const body = (
    <Card className="space-y-2 p-4 transition hover:border-primary">
      <div className="flex items-center gap-2 text-sm font-semibold text-foreground">{icon} {title}</div>
      {entries.length === 0 ? (
        <p className="text-xs text-muted-foreground">None yet.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {entries.map(([status, count]) => (
            <li key={status} className="flex justify-between">
              <span className="text-muted-foreground">{status}</span>
              <span className="font-medium tabular-nums">{count}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
  return href ? <Link href={href} className="block">{body}</Link> : body;
}
