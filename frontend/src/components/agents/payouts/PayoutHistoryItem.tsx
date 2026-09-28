import { Button } from "@3rdparty/ui/button";
import { StatusPill } from "@components/ui/StatusPill";
import { formatMinor } from "@lib/utils";
import { Payout, PayoutAction, PayoutStatus } from "@/types/payout";

/** What an agent is told while their payout waits on finance or the bank. */
const STATUS_NOTE: Partial<Record<PayoutStatus, string>> = {
  [PayoutStatus.APPROVED]: "Goes out in the next payout run.",
  [PayoutStatus.PROCESSING]: "Sent to your bank; waiting for it to confirm.",
  // The funds are still reserved: finance retries the transfer or releases them.
  [PayoutStatus.FAILED]: "The bank didn't accept the transfer. Our finance team is looking into it.",
};

/** One withdrawal in an agent's history: what they asked for, the fee, and what reaches the bank. */
export function PayoutHistoryItem({ payout, onCancel }: { payout: Payout; onCancel: () => void }) {
  const note = STATUS_NOTE[payout.status];
  return (
    <li className="flex items-start justify-between gap-3 p-3 text-sm" data-testid={`payout-${payout.id}`}>
      <div className="min-w-0 space-y-0.5">
        <p className="font-semibold tabular-nums">{formatMinor(payout.netMinor, payout.currency)}</p>
        <p className="text-xs text-muted-foreground">
          {formatMinor(payout.amountMinor, payout.currency)} less {formatMinor(payout.feeMinor, payout.currency)} fee
        </p>
        <p className="truncate text-xs text-muted-foreground">{payout.bankName} · {payout.accountNumber}</p>
        {note && <p className="text-xs text-muted-foreground" data-testid={`payout-${payout.id}-note`}>{note}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <StatusPill status={payout.status} />
        {payout.allowedActions.includes(PayoutAction.CANCEL) && (
          <Button variant="ghost" size="sm" onClick={onCancel} data-testid={`payout-${payout.id}-cancel`}>Cancel</Button>
        )}
      </div>
    </li>
  );
}
