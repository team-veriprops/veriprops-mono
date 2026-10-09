import { formatMinor, humanizeEnumLabel } from "@lib/utils";
import { CloseReason, ClosureQuote, ClosureResult } from "@/types/closure";

/** The close reasons an admin picks from, in the order a case usually meets them. */
export const CLOSE_REASONS: { value: CloseReason; label: string; hint: string }[] = [
  { value: CloseReason.CUSTOMER_WITHDREW, label: "Customer withdrew", hint: "Refund less the surcharge before work starts; nothing after." },
  { value: CloseReason.DUPLICATE, label: "Duplicate case or payment", hint: "Full refund." },
  { value: CloseReason.CANNOT_DELIVER, label: "We cannot deliver", hint: "Full refund; the case ends as failed." },
  { value: CloseReason.FRAUD, label: "Fraudulent submission", hint: "No refund." },
  { value: CloseReason.PROPERTY_INACCESSIBLE, label: "Property inaccessible", hint: "Refund the amount you set, on the evidence." },
];

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

/**
 * The confirmation an admin must accept before a paid case closes: every consequence the
 * backend's quote states — the refund, Finance's approval, the hold, each agent's outcome —
 * spelled out before anything happens.
 */
export function closureConfirmation(quote: ClosureQuote): { title: string; description: string; confirmLabel: string } {
  const ending = humanizeEnumLabel(quote.resultingStatus).toLowerCase();
  const paid = quote.agents.filter((a) => a.paid).length;
  const cancelled = quote.agents.length - paid;
  const agents =
    `${plural(paid, "agent", "agents")} with submitted work will be paid; ` +
    `${plural(cancelled, "unfinished task", "unfinished tasks")} will be cancelled.`;
  if (quote.requiresApproval) {
    const amount = formatMinor(quote.refundMinor, quote.currency);
    return {
      title: "Close this paid case?",
      description:
        `The customer is refunded ${amount} once Finance approves. Until then the case is on hold and its ` +
        `agents are told to stop. When approved, it ends as ${ending}: ${agents} This cannot be undone.`,
      confirmLabel: `Close and request ${amount} refund`,
    };
  }
  return {
    title: "Close this paid case?",
    description: `Nothing is refunded. The case ends now as ${ending}: ${agents} This cannot be undone.`,
    confirmLabel: "Close case now",
  };
}

/** What to tell the admin once the close went through. */
export function closeOutcomeMessage(result: ClosureResult): string {
  if (result.onHold) {
    return `Case on hold. The ${formatMinor(result.refundMinor, result.currency)} refund is waiting for Finance's approval.`;
  }
  return `Case closed as ${humanizeEnumLabel(result.status).toLowerCase()}. Nothing was refunded.`;
}
