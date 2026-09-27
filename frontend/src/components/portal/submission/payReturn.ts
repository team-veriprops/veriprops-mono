import { Payment, PaymentCheckoutKind, PaymentPurpose, PaymentStatus } from "@/types/verification";

/** What the pay page does with the latest payment the backend reconciled for it. */
export enum PayReturn {
  /** No payment yet: offer "Pay now". */
  NONE = "NONE",
  /** The initial charge settled: go to the confirmation page. */
  PAID = "PAID",
  /** A re-check or upgrade charge settled: go back to the verification. */
  SECONDARY_PAID = "SECONDARY_PAID",
  /** A hosted charge the gateway has not settled yet: keep asking for a short while. */
  CONFIRMING = "CONFIRMING",
  /** The charge failed at the gateway: offer a fresh attempt. */
  FAILED = "FAILED",
  /** An open stub charge: resume its deterministic confirm step. */
  STUB_PENDING = "STUB_PENDING",
}

/** Maps the backend's payment status onto the pay page's next step. The page never decides
 *  whether money moved; it only follows what the backend reconciled with the gateway. */
export function payReturnOutcome(payment: Payment | null | undefined): PayReturn {
  if (!payment) return PayReturn.NONE;
  if (payment.status === PaymentStatus.SUCCEEDED) {
    return payment.purpose === PaymentPurpose.INITIAL ? PayReturn.PAID : PayReturn.SECONDARY_PAID;
  }
  if (payment.status === PaymentStatus.FAILED) return PayReturn.FAILED;
  if (payment.status === PaymentStatus.REFUNDED) return PayReturn.NONE;
  return payment.checkoutKind === PaymentCheckoutKind.STUB ? PayReturn.STUB_PENDING : PayReturn.CONFIRMING;
}
