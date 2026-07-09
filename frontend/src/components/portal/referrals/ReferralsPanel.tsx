"use client";

import { useMemo } from "react";
import { Gift } from "lucide-react";
import { Card } from "@3rdparty/ui/card";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { CopyText } from "@components/ui/CopyText";
import { StatCard } from "@components/ui/StatCard";
import { useReferralSummaryQuery } from "./libs/useReferralQueries";
import { ReferralCredit, ReferralCreditStatus, ReferralSummary } from "@/types/referral";
import { formatMinor } from "@lib/utils";

const STATUS_LABEL: Record<ReferralCreditStatus, string> = {
  [ReferralCreditStatus.PENDING]: "Pending",
  [ReferralCreditStatus.CLEARED]: "Cleared",
  [ReferralCreditStatus.VOID]: "Not eligible",
};

const STATUS_TONE: Record<ReferralCreditStatus, string> = {
  [ReferralCreditStatus.PENDING]: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  [ReferralCreditStatus.CLEARED]: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  [ReferralCreditStatus.VOID]: "bg-muted text-muted-foreground",
};

/**
 * Referral hub (§17.1). Shows the customer's shareable link, their credit balances
 * (all backend-derived), and the reward history. Credit applies automatically at
 * checkout — nothing to redeem.
 */
export default function ReferralsPanel() {
  const { data, isLoading, isError } = useReferralSummaryQuery();

  return (
    <div className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6" data-testid="portal-referrals">
      <div className="flex items-center gap-2">
        <Gift className="size-6 text-primary" aria-hidden />
        <h1 className="text-2xl font-bold text-foreground">Refer &amp; earn</h1>
      </div>

      <AsyncStateComponent<ReferralSummary> isLoading={isLoading} isError={isError} data={data}>
        {(summary) => <ReferralBody summary={summary} />}
      </AsyncStateComponent>
    </div>
  );
}

function ReferralBody({ summary }: { summary: ReferralSummary }) {
  const link = useMemo(
    () => (typeof window !== "undefined" ? `${window.location.origin}${summary.sharePath}` : summary.sharePath),
    [summary.sharePath],
  );

  return (
    <div className="space-y-6">
      <Card className="space-y-3 p-5">
        <p className="text-sm text-muted-foreground">
          Share your link. When a friend completes their first verification, you earn{" "}
          <span className="font-semibold text-foreground">{formatMinor(summary.referralCreditNgn * 100)}</span>{" "}
          in credit — applied automatically at your next checkout.
        </p>
        <div className="rounded-lg border border-border bg-muted/40 p-2">
          <CopyText text={link} />
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <StatCard label="Available credit" value={formatMinor(summary.availableCreditMinor) ?? "—"} tone="success" />
        <StatCard label="Pending" value={formatMinor(summary.pendingCreditMinor) ?? "—"} tone="warning" />
        <StatCard label="Lifetime earned" value={formatMinor(summary.lifetimeCreditMinor) ?? "—"} />
      </div>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Referral history</h2>
        {summary.credits.length === 0 ? (
          <Card className="p-8 text-center text-sm text-muted-foreground">
            No referrals yet — share your link to start earning.
          </Card>
        ) : (
          <ul className="space-y-2">
            {summary.credits.map((c) => (
              <CreditRow key={c.id} credit={c} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CreditRow({ credit }: { credit: ReferralCredit }) {
  return (
    <li>
      <Card className="flex items-center justify-between gap-3 p-4">
        <div className="min-w-0 space-y-1">
          <p className="font-medium text-foreground">{formatMinor(credit.amountMinor)}</p>
          <p className="text-xs text-muted-foreground">
            {new Date(credit.dateCreated).toLocaleDateString()}
          </p>
        </div>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_TONE[credit.status]}`}>
          {STATUS_LABEL[credit.status]}
        </span>
      </Card>
    </li>
  );
}
