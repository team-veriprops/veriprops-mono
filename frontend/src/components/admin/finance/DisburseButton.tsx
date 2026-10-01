"use client";

import { toast } from "sonner";
import { Send } from "lucide-react";
import { Button } from "@3rdparty/ui/button";
import { formatMinor } from "@lib/utils";
import { getErrorMessage } from "@lib/errors";
import { DisbursementOutcome } from "@/types/payout";
import { useDisbursementQueueQuery, useDisburseMutation } from "./libs/useFinanceQueries";

/** What a finished batch did, in one sentence. */
export function disbursementSummary(o: DisbursementOutcome): string {
  const parts = [`${o.paid} paid`];
  if (o.failed) parts.push(`${o.failed} failed`);
  if (o.inFlight) parts.push(`${o.inFlight} still with the bank`);
  const sentence = parts.join(", ") + ".";
  return o.remaining ? `${sentence} ${o.remaining} more waiting — disburse again to send them.` : sentence;
}

/** The button's label: what a press would do right now. */
export function disburseLabel(count: number, totalMinor: number, inFlight: number): string {
  if (count > 0) return `Disburse ${count} approved (${formatMinor(totalMinor)})`;
  if (inFlight > 0) return `Check ${inFlight} transfer${inFlight === 1 ? "" : "s"} with the bank`;
  return "Nothing to disburse";
}

/**
 * Finance's "disburse" button (§15.1): sends every approved payout now, the same batch the
 * daily sweep runs. Its label is the queue — how many, and what they will draw from the
 * gateway balance — so finance can top the balance up first. With nothing approved it still
 * runs while transfers are in flight: the batch is also what settles a transfer whose webhook
 * never came, and where no scheduler runs, this press is the only thing that does.
 */
export default function DisburseButton() {
  const { data: queue } = useDisbursementQueueQuery();
  const disburse = useDisburseMutation();
  const count = queue?.count ?? 0;
  const inFlight = queue?.inFlight ?? 0;

  const run = () =>
    disburse.mutate(undefined, {
      onSuccess: (res) => {
        const outcome = res.data;
        if (!outcome) return;
        (outcome.failed ? toast.warning : toast.success)(disbursementSummary(outcome));
      },
      onError: (e: unknown) => toast.error(getErrorMessage(e, "Could not run the disbursement.")),
    });

  return (
    <Button onClick={run} disabled={(count === 0 && inFlight === 0) || disburse.isPending} data-testid="payout-disburse">
      <Send className="size-4" aria-hidden />
      {disburseLabel(count, queue?.totalMinor ?? 0, inFlight)}
    </Button>
  );
}
