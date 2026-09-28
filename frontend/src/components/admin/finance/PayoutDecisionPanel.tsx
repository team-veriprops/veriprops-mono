"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { StatusPill } from "@components/ui/StatusPill";
import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { getErrorMessage } from "@lib/errors";
import { AdminPayout, PayoutAction } from "@/types/payout";
import { FinancePayoutAction, usePayoutDecisionMutation } from "./libs/useFinanceQueries";

/** Each finance action's button, in the order the panel shows them. */
const ACTION_BUTTONS: { action: FinancePayoutAction; label: string; done: string; variant: "default" | "outline" | "destructive" }[] = [
  { action: PayoutAction.APPROVE, label: "Approve", done: "Payout approved for the next run.", variant: "default" },
  { action: PayoutAction.RETRY, label: "Retry transfer", done: "Transfer queued for the next run.", variant: "default" },
  { action: PayoutAction.HOLD, label: "Hold", done: "Payout held.", variant: "outline" },
  { action: PayoutAction.ADJUST, label: "Adjust", done: "Adjustment recorded.", variant: "outline" },
  { action: PayoutAction.REJECT, label: "Reject", done: "Payout rejected; the funds are back in the agent's balance.", variant: "destructive" },
];

/** Where the transfer stands, for a payout that has one. */
function TransferTrail({ payout }: { payout: AdminPayout }) {
  if (!payout.transferReference) return null;
  return (
    <section className="space-y-1 rounded-lg border p-3 text-xs" data-testid="payout-transfer">
      <p><span className="text-muted-foreground">Transfer reference: </span>{payout.transferReference}</p>
      {payout.gatewayTransferId && (
        <p><span className="text-muted-foreground">Gateway id: </span>{payout.gatewayTransferId}</p>
      )}
      <p><span className="text-muted-foreground">Attempts: </span>{payout.transferAttempts}</p>
      {payout.failureReason && (
        <p className="text-destructive" data-testid="payout-failure-reason">
          <span className="font-medium">Why it failed: </span>{payout.failureReason}
        </p>
      )}
    </section>
  );
}

/** A finance decision on one payout (§15.1). Offers exactly the moves the backend lists in
 * `allowedActions`, so nothing here can ask for a transition the backend would refuse. */
export default function PayoutDecisionPanel({ payout, onDone }: { payout: AdminPayout; onDone: () => void }) {
  const decide = usePayoutDecisionMutation();
  const [note, setNote] = useState("");
  const [adjustment, setAdjustment] = useState("");
  const allowed = new Set(payout.allowedActions);
  const buttons = ACTION_BUTTONS.filter((b) => allowed.has(b.action));

  const run = (action: FinancePayoutAction, done: string) => {
    const req = {
      note: note || undefined,
      adjustmentMinor: action === PayoutAction.ADJUST && adjustment ? Math.round(Number(adjustment) * 100) : undefined,
    };
    decide.mutate(
      { action, payoutId: payout.id, req },
      {
        onSuccess: () => { toast.success(done); onDone(); },
        onError: (e: unknown) => toast.error(getErrorMessage(e, "Could not update the payout.")),
      },
    );
  };

  return (
    <div className="space-y-4 p-4 text-sm">
      <section className="rounded-lg border p-3">
        <p className="text-lg font-semibold tabular-nums">{formatMinor(payout.netMinor, payout.currency)}</p>
        <p className="text-xs text-muted-foreground" data-testid="payout-breakdown">
          {formatMinor(payout.amountMinor, payout.currency)}
          {payout.adjustmentMinor !== 0 && ` ${payout.adjustmentMinor > 0 ? "+" : "−"} ${formatMinor(Math.abs(payout.adjustmentMinor), payout.currency)} adjustment`}
          {" "}− {formatMinor(payout.feeMinor, payout.currency)} fee
        </p>
        <p className="mt-1 text-muted-foreground">{payout.bankName} · {payout.accountNumber} · {payout.accountName}</p>
        <div className="mt-2"><StatusPill status={payout.status} /></div>
      </section>

      <TransferTrail payout={payout} />

      {buttons.length === 0 ? (
        <p className="text-muted-foreground" data-testid="payout-no-actions">
          {humanizeEnumLabel(payout.status)} — nothing to decide here.
        </p>
      ) : (
        <>
          <div className="space-y-2">
            <Label htmlFor="payout-note">Note (hold reason / correction)</Label>
            <Input id="payout-note" value={note} onChange={(e) => setNote(e.target.value)} />
          </div>
          {allowed.has(PayoutAction.ADJUST) && (
            <div className="space-y-2">
              <Label htmlFor="payout-adjust">Adjustment (₦, for Adjust)</Label>
              <Input id="payout-adjust" inputMode="decimal" value={adjustment} onChange={(e) => setAdjustment(e.target.value)} />
            </div>
          )}
          <div className="grid grid-cols-2 gap-2">
            {buttons.map((b) => (
              <Button key={b.action} variant={b.variant} onClick={() => run(b.action, b.done)} disabled={decide.isPending}
                data-testid={`payout-${b.action.toLowerCase()}`}>
                {b.label}
              </Button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
