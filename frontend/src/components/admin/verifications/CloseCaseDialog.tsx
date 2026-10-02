"use client";

import { useId, useState } from "react";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { Input } from "@3rdparty/ui/input";
import { Label } from "@3rdparty/ui/label";
import { Textarea } from "@3rdparty/ui/textarea";
import DetailDrawer from "@components/ui/DetailDrawer";
import { ConfirmDialog } from "@components/ui/ConfirmDialog";
import { getErrorMessage } from "@lib/errors";
import { formatMinor, humanizeEnumLabel, majorToMinor } from "@lib/utils";
import { CloseReason } from "@/types/closure";
import { TransactionCurrency } from "@/types/models";
import { CLOSE_REASONS, closeOutcomeMessage, closureConfirmation } from "./libs/closure";
import { useCloseCaseMutation, useClosureQuoteQuery } from "./libs/useAdminVerificationQueries";

const NOTE_MIN = 5;

interface CloseCaseDialogProps {
  verificationId: string;
  vid: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** The reason the dialog opens on (report review opens on "we cannot deliver"). */
  initialReason?: CloseReason;
  /** The case's contractual currency, for the refund field before a quote has arrived. */
  currency?: TransactionCurrency;
}

/**
 * Close a paid case (§6.4). The admin picks a reason and says why; the backend quotes the
 * exact refund, how the case ends and what happens to each agent; the admin then confirms that
 * quote in a dialog that states every consequence. A refund is never sent from here: it waits
 * for Finance, and the case is on hold until then.
 */
export function CloseCaseDialog({
  verificationId, vid, open, onOpenChange, initialReason = CloseReason.CUSTOMER_WITHDREW, currency = TransactionCurrency.NGN,
}: CloseCaseDialogProps) {
  const [reason, setReason] = useState<CloseReason>(initialReason);
  const [note, setNote] = useState("");
  const [amountText, setAmountText] = useState("");
  const [evidenceRef, setEvidenceRef] = useState("");
  const [confirming, setConfirming] = useState(false);
  const ids = { reason: useId(), note: useId(), amount: useId(), evidence: useId() };

  const inaccessible = reason === CloseReason.PROPERTY_INACCESSIBLE;
  const amountMinor = inaccessible ? majorToMinor(amountText) : undefined;
  const quoteReady = open && (!inaccessible || amountMinor !== undefined);
  const quote = useClosureQuoteQuery(verificationId, reason, amountMinor, quoteReady);
  const close = useCloseCaseMutation(verificationId);

  const ready =
    !!quote.data && note.trim().length >= NOTE_MIN && (!inaccessible || (amountMinor !== undefined && !!evidenceRef.trim()));

  const submit = async () => {
    try {
      const res = await close.mutateAsync({
        reason, note: note.trim(),
        ...(inaccessible ? { amountMinor, evidenceRef: evidenceRef.trim() } : {}),
      });
      setConfirming(false);
      onOpenChange(false);
      if (res.data) toast.success(closeOutcomeMessage(res.data));
    } catch (err) {
      setConfirming(false);
      toast.error(getErrorMessage(err, "The case could not be closed."));
    }
  };

  return (
    <>
      <DetailDrawer title="Close this case" reference={vid} open={open} onOpenChange={onOpenChange}
        description="Paid cases are closed, not cancelled: the refund follows the refund rules and waits for Finance.">
        <div className="space-y-4" data-testid="close-case">
          <div className="space-y-1">
            <Label htmlFor={ids.reason}>Why is it closing?</Label>
            <select id={ids.reason} value={reason} onChange={(e) => setReason(e.target.value as CloseReason)}
              className="h-9 w-full rounded-md border bg-background px-3 text-sm" data-testid="close-case-reason">
              {CLOSE_REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
            <p className="text-xs text-muted-foreground">{CLOSE_REASONS.find((r) => r.value === reason)?.hint}</p>
          </div>

          {inaccessible && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor={ids.amount}>Refund ({quote.data?.currency ?? currency})</Label>
                <Input id={ids.amount} inputMode="decimal" value={amountText} onChange={(e) => setAmountText(e.target.value)}
                  data-testid="close-case-amount" />
              </div>
              <div className="space-y-1">
                <Label htmlFor={ids.evidence}>Evidence reference</Label>
                <Input id={ids.evidence} value={evidenceRef} onChange={(e) => setEvidenceRef(e.target.value)}
                  placeholder="The geotagged access attempt" data-testid="close-case-evidence" />
              </div>
            </div>
          )}

          <div className="space-y-1">
            <Label htmlFor={ids.note}>What happened</Label>
            <Textarea id={ids.note} value={note} onChange={(e) => setNote(e.target.value)} rows={3}
              placeholder="Recorded on the case and shown to Finance." data-testid="close-case-note" />
          </div>

          <div className="rounded-lg border p-3 text-sm" data-testid="close-case-quote" aria-live="polite">
            {quote.isFetching ? (
              <p className="flex items-center gap-2 text-muted-foreground"><Loader2 className="size-4 animate-spin" /> Working out the refund…</p>
            ) : quote.isError ? (
              <p className="text-destructive" role="alert">{getErrorMessage(quote.error, "The refund could not be worked out.")}</p>
            ) : quote.data ? (
              <dl className="grid grid-cols-2 gap-x-3 gap-y-1">
                <dt className="text-muted-foreground">Refund to the customer</dt>
                <dd className="font-semibold tabular-nums" data-testid="close-case-refund">{formatMinor(quote.data.refundMinor, quote.data.currency)}</dd>
                <dt className="text-muted-foreground">Paid so far</dt>
                <dd className="tabular-nums">{formatMinor(quote.data.refundableMinor, quote.data.currency)}</dd>
                <dt className="text-muted-foreground">Case ends as</dt>
                <dd>{humanizeEnumLabel(quote.data.resultingStatus)}</dd>
                <dt className="text-muted-foreground">Finance approval</dt>
                <dd>{quote.data.requiresApproval ? "Needed — the case is on hold until then" : "Not needed — nothing is refunded"}</dd>
              </dl>
            ) : (
              <p className="text-muted-foreground">Enter the refund to see what closing does.</p>
            )}
          </div>

          <Button variant="destructive" className="w-full" disabled={!ready || close.isPending}
            onClick={() => setConfirming(true)} data-testid="close-case-review">
            Review and close
          </Button>
        </div>
      </DetailDrawer>

      {quote.data && (
        <ConfirmDialog
          open={confirming}
          onOpenChange={setConfirming}
          {...closureConfirmation(quote.data)}
          onConfirm={submit}
          destructive
          pending={close.isPending}
          testId="close-case-confirm"
        />
      )}
    </>
  );
}
