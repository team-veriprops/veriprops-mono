import { RefundOutcome } from "@/types/adminVerification";

/**
 * What to tell Finance after approving a refund: "refunded" only when the gateway took it.
 * `done` is the sentence's opening ("Refund approved"); `ok` false asks for a warning.
 */
export function refundSummary(done: string, refund: RefundOutcome | null | undefined): { ok: boolean; message: string } {
  if (!refund) return { ok: true, message: done };
  if (refund.failedPaymentIds.length) {
    return { ok: false, message: `${done}, but the gateway refused the refund. It is waiting in Finance to retry.` };
  }
  if (refund.heldPaymentIds.length) {
    return { ok: false, message: `${done}. No refund was sent: a chargeback is already returning the money.` };
  }
  return { ok: true, message: `${done} & refunded` };
}
