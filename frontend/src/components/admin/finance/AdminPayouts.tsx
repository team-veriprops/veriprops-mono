"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import DetailDrawer from "@components/ui/DetailDrawer";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { PageShell } from "@components/ui/PageShell";
import { StatusPill } from "@components/ui/StatusPill";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { Payout, PayoutStatus } from "@/types/payout";
import { Page } from "@/types/models";
import { useAdminPayoutsQuery, usePayoutDecisionMutation } from "./libs/useFinanceQueries";

const STATUSES = ["", PayoutStatus.REQUESTED, PayoutStatus.HELD, PayoutStatus.PAID, PayoutStatus.REJECTED];

/** Finance payout panel (§15.1): approve / hold / adjust / reject withdrawal requests. */
export default function AdminPayouts() {
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const { data, isLoading, isError } = useAdminPayoutsQuery(page, 10, status);
  const [selected, setSelected] = useState<Payout | null>(null);

  return (
    <PageShell
      title="Payouts"
      description="Approve, hold, adjust, or reject agent withdrawal requests."
      actions={
        <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}
          className="h-9 rounded-md border bg-background px-3 text-sm" data-testid="payout-status-filter">
          {STATUSES.map((s) => <option key={s || "all"} value={s}>{s ? humanizeEnumLabel(s) : "All"}</option>)}
        </select>
      }
    >
      <AsyncStateComponent<Page<Payout>>
        isLoading={isLoading}
        isError={isError}
        data={data}
        loadingText="Loading payouts…"
        emptyText="No payouts."
      >
        {(pageData) => (
          <>
            {pageData.items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No payouts.</p>
            ) : (
              <ul className="divide-y rounded-lg border" data-testid="admin-payouts">
                {pageData.items.map((p) => (
                  <li key={p.id}>
                    <button onClick={() => setSelected(p)}
                      className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm hover:bg-muted/50">
                      <div className="min-w-0">
                        <p className="font-semibold tabular-nums">{formatMinor(p.amountMinor, p.currency)}</p>
                        <p className="truncate text-xs text-muted-foreground">{p.bankName} · {p.accountNumber} · {p.accountName}</p>
                      </div>
                      <StatusPill status={p.status} className="shrink-0" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <div className="mt-3 flex items-center justify-between">
              <Button variant="outline" size="sm" disabled={page === 0} onClick={() => setPage((v) => Math.max(0, v - 1))}>Previous</Button>
              <span className="text-xs text-muted-foreground">Page {page + 1}</span>
              <Button variant="outline" size="sm" disabled={pageData.meta.nextPage == null} onClick={() => setPage((v) => v + 1)}>Next</Button>
            </div>
          </>
        )}
      </AsyncStateComponent>

      <DetailDrawer open={!!selected} onOpenChange={(o) => !o && setSelected(null)}
        title="Payout" reference={selected?.id ?? ""}>
        {selected && <DecisionPanel payout={selected} onDone={() => setSelected(null)} />}
      </DetailDrawer>
    </PageShell>
  );
}

function DecisionPanel({ payout, onDone }: { payout: Payout; onDone: () => void }) {
  const decide = usePayoutDecisionMutation();
  const [note, setNote] = useState("");
  const [adjustment, setAdjustment] = useState("");
  const pending = decide.isPending;
  const decided = payout.status !== PayoutStatus.REQUESTED && payout.status !== PayoutStatus.HELD;

  const run = (action: "approve" | "hold" | "adjust" | "reject") => {
    const req = {
      note: note || undefined,
      adjustmentMinor: action === "adjust" && adjustment ? Math.round(Number(adjustment) * 100) : undefined,
    };
    decide.mutate(
      { action, payoutId: payout.id, req },
      {
        onSuccess: () => { toast.success(`Payout ${action}ed.`); onDone(); },
        onError: (e: unknown) => toast.error((e as Error)?.message ?? "Could not update the payout."),
      },
    );
  };

  return (
    <div className="space-y-4 p-4 text-sm">
      <section className="rounded-lg border p-3">
        <p className="text-lg font-semibold tabular-nums">{formatMinor(payout.amountMinor, payout.currency)}</p>
        <p className="text-muted-foreground">{payout.bankName} · {payout.accountNumber} · {payout.accountName}</p>
        <div className="mt-2"><StatusPill status={payout.status} /></div>
      </section>

      {decided ? (
        <p className="text-muted-foreground">This payout has been finalised.</p>
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="payout-note">Note (hold reason / correction)</Label>
            <Input id="payout-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="payout-adjust">Adjustment (₦, for Adjust)</Label>
            <Input id="payout-adjust" inputMode="decimal" value={adjustment} onChange={(e) => setAdjustment(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button onClick={() => run("approve")} disabled={pending} data-testid="payout-approve">Approve &amp; pay</Button>
            <Button variant="outline" onClick={() => run("hold")} disabled={pending} data-testid="payout-hold">Hold</Button>
            <Button variant="outline" onClick={() => run("adjust")} disabled={pending} data-testid="payout-adjust-btn">Adjust</Button>
            <Button variant="destructive" onClick={() => run("reject")} disabled={pending} data-testid="payout-reject">Reject</Button>
          </div>
        </>
      )}
    </div>
  );
}
