"use client";

import { useState } from "react";
import { Button } from "@3rdparty/ui/button";
import DetailDrawer from "@components/ui/DetailDrawer";
import { AsyncStateComponent } from "@components/ui/AsyncStateComponent";
import { PageShell } from "@components/ui/PageShell";
import { StatusPill } from "@components/ui/StatusPill";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { AdminPayout, PayoutStatus } from "@/types/payout";
import { Page } from "@/types/models";
import { useAdminPayoutsQuery } from "./libs/useFinanceQueries";
import DisburseButton from "./DisburseButton";
import PayoutDecisionPanel from "./PayoutDecisionPanel";

// Filter order follows the lifecycle: waiting on finance, queued, with the bank, finished.
const STATUSES = [
  "", PayoutStatus.REQUESTED, PayoutStatus.HELD, PayoutStatus.APPROVED, PayoutStatus.PROCESSING,
  PayoutStatus.FAILED, PayoutStatus.PAID, PayoutStatus.REJECTED, PayoutStatus.CANCELLED,
];

/** Finance payout panel (§15.1): decide withdrawal requests, send approved ones as a batch,
 * and retry or reject transfers the bank refused. */
export default function AdminPayouts() {
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const { data, isLoading, isError } = useAdminPayoutsQuery(page, 10, status);
  const [selected, setSelected] = useState<AdminPayout | null>(null);

  return (
    <PageShell
      title="Payouts"
      description="Approve agent withdrawals, then send them to agents' banks with Disburse. Where scheduled jobs run, a daily run sends them too."
      actions={
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          {/* A toolbar filter has no visible label to bind to, so it names itself — without this
              the control is announced only as "combo box" (axe `select-name`, critical). */}
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}
            aria-label="Filter payouts by status"
            className="h-9 rounded-md border bg-background px-3 text-sm" data-testid="payout-status-filter">
            {STATUSES.map((s) => <option key={s || "all"} value={s}>{s ? humanizeEnumLabel(s) : "All"}</option>)}
          </select>
          <DisburseButton />
        </div>
      }
    >
      <AsyncStateComponent<Page<AdminPayout>>
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
                    <button onClick={() => setSelected(p)} data-testid={`admin-payout-${p.id}`}
                      className="flex w-full items-center justify-between gap-3 p-3 text-left text-sm hover:bg-muted/50">
                      <div className="min-w-0">
                        <p className="font-semibold tabular-nums">{formatMinor(p.netMinor, p.currency)}</p>
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
        {selected && <PayoutDecisionPanel payout={selected} onDone={() => setSelected(null)} />}
      </DetailDrawer>
    </PageShell>
  );
}
