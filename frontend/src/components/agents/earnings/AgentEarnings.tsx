"use client";

import { useState } from "react";
import Link from "next/link";
import { Wallet, Clock, Lock, PauseCircle, TrendingUp, Banknote } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { StatCard } from "@components/ui/StatCard";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { ROUTES } from "@/lib/routes";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { EarningJob, EarningsSummary } from "@/types/earnings";
import { Page } from "@/types/models";
import {
  useEarningJobsQuery,
  useEarningsRealtime,
  useEarningsSummaryQuery,
} from "./libs/useEarningsQueries";

const JOB_STATUS_LABEL: Record<string, string> = {
  CLEARING: "Clearing",
  AVAILABLE: "Available",
  FROZEN: "On hold",
  REVERSED: "Reversed",
};

/**
 * Agent earnings dashboard (§15.1). "Available to withdraw now" is the single hero figure;
 * clearing / reserve / lifetime / paid are the explained secondary lines. Per-job breakdown
 * below. All figures are backend-derived (D31) and never recomputed here.
 */
export default function AgentEarnings() {
  const { data: summary, isLoading, isError } = useEarningsSummaryQuery();
  const [page, setPage] = useState(0);
  const jobs = useEarningJobsQuery(page);
  useEarningsRealtime();

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold">Earnings</h1>
          <p className="text-sm text-muted-foreground">
            Money clears after a short holding period, so what you see as available is yours to withdraw.
          </p>
        </div>
        <Button asChild data-testid="earnings-withdraw-cta">
          <Link href={ROUTES.AGENT.PAYOUTS}>Withdraw</Link>
        </Button>
      </header>

      <AsyncStateComponent<EarningsSummary>
        isLoading={isLoading}
        isError={isError}
        data={summary}
        loadingText="Loading earnings…"
      >
        {(s) => (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <StatCard
              label="Available to withdraw"
              value={formatMinor(s.availableMinor, s.currency) ?? "—"}
              icon={Wallet}
              tone="success"
              hint="Cleared and yours now"
              href={ROUTES.AGENT.PAYOUTS}
              className="sm:col-span-2 lg:col-span-1"
            />
            <StatCard label="Clearing" value={formatMinor(s.clearingMinor, s.currency) ?? "—"} icon={Clock}
              hint="Earned, clearing soon" />
            <StatCard label="In reserve" value={formatMinor(s.inReserveMinor, s.currency) ?? "—"} icon={Lock}
              hint="Held until the chargeback window closes" />
            <StatCard label="On hold" value={formatMinor(s.onHoldMinor, s.currency) ?? "—"} icon={PauseCircle}
              tone={s.onHoldMinor > 0 ? "warning" : "default"} hint="Frozen by a dispute" />
            <StatCard label="Lifetime earned" value={formatMinor(s.lifetimeEarnedMinor, s.currency) ?? "—"} icon={TrendingUp} />
            <StatCard label="Total paid out" value={formatMinor(s.totalPaidMinor, s.currency) ?? "—"} icon={Banknote} />
          </div>
        )}
      </AsyncStateComponent>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold">Per-job breakdown</h2>
        <AsyncStateComponent<Page<EarningJob>>
          isLoading={jobs.isLoading}
          isError={jobs.isError}
          data={jobs.data}
          loadingText="Loading jobs…"
          emptyText="No commissions yet."
        >
          {(pageData) => (
            <>
              {pageData.items.length === 0 ? (
                <p className="text-sm text-muted-foreground">No commissions yet.</p>
              ) : (
                <ul className="divide-y rounded-lg border" data-testid="earning-jobs">
                  {pageData.items.map((j) => (
                    <li key={j.id} className="flex items-center justify-between gap-3 p-3 text-sm">
                      <div className="min-w-0">
                        <p className="truncate font-medium">
                          {humanizeEnumLabel(j.role)} · {humanizeEnumLabel(j.tier)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {JOB_STATUS_LABEL[j.status] ?? j.status}
                          {j.reserveAmountMinor > 0 && ` · reserve ${formatMinor(j.reserveAmountMinor)}`}
                        </p>
                      </div>
                      <span className="shrink-0 font-semibold tabular-nums">{formatMinor(j.amountMinor)}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-3 flex items-center justify-between">
                <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
                  Previous
                </Button>
                <span className="text-xs text-muted-foreground">Page {page + 1}</span>
                <Button variant="outline" size="sm" disabled={pageData.meta.nextPage == null}
                  onClick={() => setPage((p) => p + 1)}>
                  Next
                </Button>
              </div>
            </>
          )}
        </AsyncStateComponent>
      </section>
    </div>
  );
}
